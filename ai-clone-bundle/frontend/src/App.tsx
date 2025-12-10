import { BrowserRouter, Routes, Route } from "react-router-dom"
import { Layout } from "@/components/layout/Layout"
import TestChat from "@/pages/TestChat"
import CloneSettings from "@/pages/CloneSettings"
import RagKnowledge from "@/pages/RagKnowledge"
import Messengers from "@/pages/Messengers"

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<TestChat />} />
          <Route path="settings" element={<CloneSettings />} />
          <Route path="rag" element={<RagKnowledge />} />
          <Route path="messengers" element={<Messengers />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
