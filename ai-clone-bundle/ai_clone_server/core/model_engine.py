import os
from pathlib import Path
import torch
try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

try:
    from transformers import AutoModelForCausalLM, AutoProcessor
    from peft import PeftModel
    from qwen_vl_utils import process_vision_info
except ImportError as e:
    print(f"DEBUG: Failed to import transformers/peft dependencies: {e}")
    AutoModelForCausalLM = None
    PeftModel = None

try:
    from bitsandbytes import BitsAndBytesConfig
except ImportError:
    BitsAndBytesConfig = None

class ModelEngine:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.backend = self.config_manager.get("model.backend", "llama_cpp")
        self.llm = None
        self.tokenizer = None
        self.processor = None
        self.model = None
        self.quantization_config = None
        
        self.load_model()

    def load_model(self):
        config = self.config_manager.get("model")
        base_model_path = config.get("base_model_path")
        lora_path = config.get("lora_path")
        device = config.get("device", "auto")

        print(f"Loading model with backend: {self.backend}...")

        if self.backend == "transformers":
            if AutoModelForCausalLM is None:
                print("Error: transformers/peft not installed. Running in MOCK mode.")
                return

            try:
                base_dir = Path(__file__).resolve().parents[2]

                # Resolve base model path if it is a local relative path
                if base_model_path and not os.path.isabs(base_model_path):
                    candidate = (base_dir / base_model_path).resolve()
                    if candidate.exists():
                        base_model_path = str(candidate)
                        print(f"DEBUG: Resolved base model path to {base_model_path}")

                # Resolve LoRA path relative to repo root when given as relative path
                if lora_path and not os.path.isabs(lora_path):
                    candidate = (base_dir / lora_path).resolve()
                    if candidate.exists():
                        lora_path = str(candidate)
                        print(f"DEBUG: Resolved LoRA path to {lora_path}")
                    else:
                        print(f"DEBUG: LoRA relative path {lora_path} not found at {candidate}")

                processor_source = base_model_path
                print(f"DEBUG: Loading processor from {processor_source}...")
                self.processor = AutoProcessor.from_pretrained(processor_source, trust_remote_code=True)

                self.quantization_config = self._build_quantization_config(config)
                
                # Build load kwargs based on whether quantization is enabled
                load_kwargs = {
                    "device_map": device,
                    "trust_remote_code": True,
                }
                
                # Set torch_dtype based on quantization config
                if self.quantization_config:
                    load_kwargs["quantization_config"] = self.quantization_config
                    # Use the compute dtype from quantization config
                    load_kwargs["torch_dtype"] = self.quantization_config.bnb_4bit_compute_dtype
                    print(f"DEBUG: 4-bit quantization enabled with compute_dtype={self.quantization_config.bnb_4bit_compute_dtype}")
                else:
                    # No quantization - use float16 for CUDA or auto for CPU
                    load_kwargs["torch_dtype"] = torch.float16 if torch.cuda.is_available() else "auto"
                
                # Add Flash Attention 2 for Qwen2.5-VL if available
                try:
                    load_kwargs["attn_implementation"] = "flash_attention_2"
                    print("DEBUG: Flash Attention 2 will be used")
                except Exception:
                    print("DEBUG: Flash Attention 2 not available, using default attention")
                
                print(f"DEBUG: Loading base model from {base_model_path} on {device}...")
                # Try to import the specific class for Qwen2.5-VL
                try:
                    from transformers import Qwen2_5_VLForConditionalGeneration
                    ModelClass = Qwen2_5_VLForConditionalGeneration
                except ImportError:
                    # Fallback to AutoModel if specific class not available (though it should be in dev version)
                    # or if using an older version that might support it via AutoModel
                    print("DEBUG: Qwen2_5_VLForConditionalGeneration not found, falling back to AutoModelForCausalLM (might fail)")
                    ModelClass = AutoModelForCausalLM

                self.model = ModelClass.from_pretrained(base_model_path, **load_kwargs)

                # Load LoRA
                if lora_path and os.path.exists(lora_path):
                    print(f"DEBUG: Loading LoRA adapter from {lora_path}...")
                    self.model = PeftModel.from_pretrained(self.model, lora_path)
                    # Try to load processor from adapter (may include updated tokenizer config)
                    try:
                        self.processor = AutoProcessor.from_pretrained(lora_path, trust_remote_code=True)
                        print("DEBUG: Processor loaded from LoRA adapter.")
                    except Exception as proc_err:
                        print(f"DEBUG: Failed to load processor from LoRA adapter, using base: {proc_err}")
                else:
                    print(f"DEBUG: LoRA path not found or empty: {lora_path}")

                if self.model is not None:
                    self.model = self.model.eval()
                
                print("Transformers model loaded successfully.")

            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"Failed to load transformers model: {e}. Running in MOCK mode.")
                self.model = None

        elif self.backend == "llama_cpp":
            if not base_model_path or not os.path.exists(base_model_path):
                print(f"Warning: Model not found at {base_model_path}. Running in MOCK mode.")
                return

            if Llama is None:
                print("Warning: llama-cpp-python not installed. Running in MOCK mode.")
                return

            try:
                # llama-cpp supports LoRA via lora_path arg, but it expects GGUF formatted LoRA usually
                # If user provided a safetensors LoRA path in config for llama_cpp, it might fail or need conversion.
                # For now we assume if backend=llama_cpp, paths are correct for it.
                self.llm = Llama(
                    model_path=base_model_path,
                    lora_path=lora_path if lora_path and os.path.exists(lora_path) else None,
                    n_ctx=2048,
                    n_gpu_layers=-1,
                    verbose=False
                )
                print(f"Llama model loaded from {base_model_path}")
            except Exception as e:
                print(f"Failed to load llama model: {e}. Running in MOCK mode.")
                self.llm = None

    def _detect_optimal_compute_dtype(self):
        """
        Automatically detect the best compute dtype for the current hardware.
        Returns bfloat16 for Ampere+ GPUs (compute capability >= 8.0),
        and float16 for older GPUs.
        """
        if not torch.cuda.is_available():
            print("DEBUG: CUDA not available, defaulting to float16")
            return torch.float16
        
        try:
            # Get GPU compute capability
            device_id = 0  # Primary GPU
            compute_capability = torch.cuda.get_device_capability(device_id)
            major, minor = compute_capability
            
            gpu_name = torch.cuda.get_device_name(device_id)
            print(f"DEBUG: Detected GPU: {gpu_name} (Compute Capability: {major}.{minor})")
            
            # Ampere and newer (RTX 30xx, A100, H100, etc.) support bfloat16 natively
            # Compute capability >= 8.0
            if major >= 8:
                print("DEBUG: GPU supports bfloat16 (Ampere or newer)")
                return torch.bfloat16
            else:
                print(f"DEBUG: GPU doesn't support native bfloat16 (pre-Ampere). Using float16.")
                return torch.float16
                
        except Exception as e:
            print(f"DEBUG: Failed to detect GPU capability: {e}. Defaulting to float16.")
            return torch.float16

    def _build_quantization_config(self, model_config):
        import platform
        
        quant_cfg = model_config.get("quantization") or {}
        enable_4bit = quant_cfg.get("enable_4bit", True)

        if not enable_4bit:
            return None

        if BitsAndBytesConfig is None:
            print("Warning: bitsandbytes not installed. Skipping 4-bit quantization.")
            return None
        
        # macOS doesn't support bitsandbytes
        if platform.system() == "Darwin":
            print("Warning: 4-bit quantization is not supported on macOS. Skipping.")
            return None

        device = model_config.get("device", "auto")
        if isinstance(device, str) and device.lower() == "cpu":
            print("Warning: 4-bit quantization requested but device=cpu. Skipping.")
            return None

        if not torch.cuda.is_available():
            print("Warning: CUDA is not available. Skipping 4-bit quantization.")
            return None

        # Auto-detect optimal compute dtype based on hardware
        compute_dtype_name = quant_cfg.get("compute_dtype", "auto")
        
        if compute_dtype_name == "auto":
            print("DEBUG: Auto-detecting optimal compute dtype based on GPU...")
            compute_dtype = self._detect_optimal_compute_dtype()
        else:
            # Manual override from config
            compute_dtype = getattr(torch, compute_dtype_name, torch.float16)
            print(f"DEBUG: Using manually specified compute_dtype: {compute_dtype}")
        
        quant_type = quant_cfg.get("quant_type", "nf4")
        use_double_quant = quant_cfg.get("use_double_quant", True)

        print(f"DEBUG: Building quantization config: quant_type={quant_type}, compute_dtype={compute_dtype}, double_quant={use_double_quant}")

        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type=quant_type,
            bnb_4bit_compute_dtype=compute_dtype,
            bnb_4bit_use_double_quant=use_double_quant,
        )

    def generate(self, user_message: str, history: list = None, system_prompt: str = None) -> str:
        if system_prompt is None:
            system_prompt = self.config_manager.get("clone.system_prompt", "")

        # MOCK MODE
        if (self.backend == "transformers" and self.model is None) or \
           (self.backend == "llama_cpp" and self.llm is None):
            return f"[MOCK] I received your message: '{user_message}'. System prompt was: '{system_prompt[:20]}...'"

        # TRANSFORMERS GENERATION
        if self.backend == "transformers":
            if self.processor is None:
                return "Error generating response (transformers): processor not initialized"
            try:
                messages = [{"role": "system", "content": system_prompt}]
                # Add history if provided
                if history:
                    messages.extend(history)
                messages.append({"role": "user", "content": user_message})
                
                # Prepare inputs
                text = self.processor.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
                
                # Qwen2-VL specific processing (even for text only)
                # If we had images, we'd pass them here.
                inputs = self.processor(
                    text=[text],
                    images=None,
                    videos=None,
                    padding=True,
                    return_tensors="pt",
                )
                inputs = inputs.to(self.model.device)

                # Generate
                generated_ids = self.model.generate(**inputs, max_new_tokens=self.config_manager.get("model.max_tokens", 512))
                
                # Trim input tokens
                generated_ids_trimmed = [
                    out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
                ]
                
                output_text = self.processor.batch_decode(
                    generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
                )
                
                return output_text[0]
            except Exception as e:
                return f"Error generating response (transformers): {str(e)}"

        # LLAMA_CPP GENERATION
        elif self.backend == "llama_cpp":
            try:
                messages = [{"role": "system", "content": system_prompt}]
                # Add history if provided
                if history:
                    messages.extend(history)
                messages.append({"role": "user", "content": user_message})
                response = self.llm.create_chat_completion(
                    messages=messages,
                    max_tokens=self.config_manager.get("model.max_tokens", 512),
                    temperature=self.config_manager.get("model.temperature", 0.7),
                )
                return response["choices"][0]["message"]["content"]
            except Exception as e:
                return f"Error generating response (llama_cpp): {str(e)}"
        
        return "[Error] Unknown backend or initialization failure."
