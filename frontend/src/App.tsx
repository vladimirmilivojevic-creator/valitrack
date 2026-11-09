import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import { Loading } from "./components/ui";
import { useAuth } from "./lib/auth";

const Login = lazy(() => import("./pages/Login"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Applications = lazy(() => import("./pages/Applications"));
const ApplicationDetail = lazy(() => import("./pages/ApplicationDetail"));
const RunPage = lazy(() => import("./pages/RunPage"));
const Changes = lazy(() => import("./pages/Changes"));
const ChangeDetail = lazy(() => import("./pages/ChangeDetail"));
const Deviations = lazy(() => import("./pages/Deviations"));
const Training = lazy(() => import("./pages/Training"));
const Support = lazy(() => import("./pages/Support"));
const Reports = lazy(() => import("./pages/Reports"));
const Audit = lazy(() => import("./pages/Audit"));
const Users = lazy(() => import("./pages/Users"));
const About = lazy(() => import("./pages/About"));

function Protected() {
  const { user, loading } = useAuth();
  if (loading) return <Loading label="Starting" />;
  if (!user) return <Navigate to="/login" replace />;
  return <Shell />;
}

export default function App() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<Protected />}>
          <Route index element={<Dashboard />} />
          <Route path="applications" element={<Applications />} />
          <Route path="applications/:id" element={<ApplicationDetail />} />
          <Route path="runs/:id" element={<RunPage />} />
          <Route path="changes" element={<Changes />} />
          <Route path="changes/:id" element={<ChangeDetail />} />
          <Route path="deviations" element={<Deviations />} />
          <Route path="training" element={<Training />} />
          <Route path="support" element={<Support />} />
          <Route path="reports" element={<Reports />} />
          <Route path="audit" element={<Audit />} />
          <Route path="admin/users" element={<Users />} />
          <Route path="about" element={<About />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
