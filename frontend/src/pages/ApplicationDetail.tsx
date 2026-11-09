import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { History } from "../components/History";
import { Chip, ErrorNote, Loading, PageHeader, RiskChip, StatusChip, Tabs, Term } from "../components/ui";
import { api } from "../lib/api";
import type { Application } from "../lib/types";
import Config from "./application/Config";
import Executions from "./application/Executions";
import Overview from "./application/Overview";
import People from "./application/People";
import Requirements from "./application/Requirements";
import Tests from "./application/Tests";
import Traceability from "./application/Traceability";

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "requirements", label: "Requirements and risk" },
  { key: "tests", label: "Test cases" },
  { key: "trace", label: "Traceability" },
  { key: "runs", label: "Executions" },
  { key: "config", label: "Configuration" },
  { key: "people", label: "People and training" },
  { key: "history", label: "History" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

export default function ApplicationDetail() {
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const initial = (params.get("tab") as TabKey | null) ?? "overview";
  const [tab, setTab] = useState<TabKey>(TABS.some((t) => t.key === initial) ? initial : "overview");
  const { data: app, error, isLoading } = useQuery({
    queryKey: ["application", id],
    queryFn: () => api.get<Application>(`/applications/${id}`),
  });

  if (isLoading) return <Loading />;
  if (error || !app) return <ErrorNote error={error} />;

  const change = (key: TabKey) => {
    setTab(key);
    setParams(key === "overview" ? {} : { tab: key }, { replace: true });
  };

  return (
    <>
      <PageHeader
        crumbs={[{ to: "/applications", label: "Applications" }]}
        eyebrow={app.code}
        title={app.name}
        subtitle={app.description}
        actions={
          <>
            <Chip tone="neutral" outline>
              <Term k="GAMP">GAMP</Term> {app.gamp_category} · {app.gamp_name}
            </Chip>
            <RiskChip level={app.risk_class} />
            {app.live_version && <StatusChip status="validated" label={`Live v${app.live_version.version}`} />}
            {app.working_version && <StatusChip status="in_validation" label={`v${app.working_version.version} in validation`} />}
          </>
        }
      />
      <Tabs tabs={TABS.map((t) => ({ key: t.key, label: t.label }))} value={tab} onChange={change} />
      {tab === "overview" && <Overview app={app} />}
      {tab === "requirements" && <Requirements app={app} />}
      {tab === "tests" && <Tests app={app} />}
      {tab === "trace" && <Traceability app={app} />}
      {tab === "runs" && <Executions app={app} />}
      {tab === "config" && <Config app={app} />}
      {tab === "people" && <People app={app} />}
      {tab === "history" && (
        <div className="panel">
          <div className="panel__head"><h2>History of this application</h2></div>
          <History entityType="application" entityId={app.id} />
        </div>
      )}
    </>
  );
}
