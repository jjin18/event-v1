import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import UnifiedLogin from "./UnifiedLogin.jsx";
import JudgeApp from "./judge/JudgeApp.jsx";
import AdminWorkspace from "./admin/AdminApp.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<UnifiedLogin />} />
      <Route path="/judge" element={<JudgeApp />} />
      <Route path="/admin/*" element={<AdminWorkspace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
