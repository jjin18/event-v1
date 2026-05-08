import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import JudgeApp from "./judge/JudgeApp.jsx";
import AdminApp from "./admin/AdminApp.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/judge/*" element={<JudgeApp />} />
      <Route path="/admin/*" element={<AdminApp />} />
      <Route path="/" element={<Navigate to="/judge" replace />} />
      <Route path="*" element={<Navigate to="/judge" replace />} />
    </Routes>
  );
}
