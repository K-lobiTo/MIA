import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { MODULES } from "./modules";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/inventario" replace />} />
        {MODULES.map((module) => (
          <Route key={module.path} path={module.path} element={module.element} />
        ))}
        <Route path="*" element={<Navigate to="/inventario" replace />} />
      </Route>
    </Routes>
  );
}
