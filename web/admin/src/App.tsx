import { Navigate, Route, Routes } from "react-router-dom";
import { LoginScreen } from "./components/LoginScreen";
import { Layout } from "./components/Layout";
import { useAccessState } from "./auth/session";
import { MODULES } from "./modules";

export function App() {
  const state = useAccessState();
  // Sin sesión (o con el acceso rechazado) no se monta ninguna ruta ni se pide ningún dato.
  if (state.kind !== "activa") return <LoginScreen state={state} />;
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
