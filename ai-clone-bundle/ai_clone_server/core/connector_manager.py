from ai_clone_server.connectors.telegram_connector import TelegramConnector

class ConnectorManager:
    def __init__(self, config_manager, model_engine, rag_engine):
        self.config_manager = config_manager
        self.model_engine = model_engine
        self.rag_engine = rag_engine
        self.telegram_connector = None

    def update_connectors(self):
        """
        Checks config and starts/stops connectors.
        """
        telegram_config = self.config_manager.get("messengers.telegram")
        
        if telegram_config and telegram_config.get("enabled"):
            bots = telegram_config.get("bots", [])
            if bots:
                # For MVP, we only support the first bot
                token = bots[0].get("token")
                if token:
                    if not self.telegram_connector:
                        self.start_telegram(token)
                    elif self.telegram_connector.token != token:
                        # Token changed, restart
                        self.stop_telegram()
                        self.start_telegram(token)
                else:
                    self.stop_telegram()
            else:
                self.stop_telegram()
        else:
            self.stop_telegram()

    def start_telegram(self, token):
        print(f"Starting Telegram Connector with token {token[:5]}...")
        self.telegram_connector = TelegramConnector(token, self.model_engine, self.rag_engine)
        self.telegram_connector.start()

    def stop_telegram(self):
        if self.telegram_connector:
            print("Stopping Telegram Connector...")
            self.telegram_connector.stop()
            self.telegram_connector = None
