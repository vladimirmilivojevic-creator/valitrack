import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { GateChecklist, LifecycleStepper } from "./Gate";
import { SignatureModal } from "./Signing";
import { RiskChip, StatusChip } from "./ui";

vi.mock("../lib/auth", () => ({
  useAuth: () => ({ user: { full_name: "Eva Mayr", role: "qa_manager" }, can: () => true }),
}));
vi.mock("../lib/queries", () => ({
  useMeta: () => ({ data: { roles: { qa_manager: "QA manager" } } }),
}));

describe("StatusChip and RiskChip", () => {
  it("always shows a word, never only a colour", () => {
    render(<><StatusChip status="failed" /><StatusChip status="pending_approval" /><RiskChip level="high" /></>);
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("Awaiting approval")).toBeInTheDocument();
    expect(screen.getByText("High risk")).toBeInTheDocument();
  });

  it("says when something is not rated", () => {
    render(<RiskChip level={null} />);
    expect(screen.getByText("not rated")).toBeInTheDocument();
  });
});

describe("GateChecklist", () => {
  const gate = {
    version_id: 1, ready_for_report: false, passed: false, state_hash: "abc",
    checks: [
      { key: "coverage", label: "Every requirement has a test", passed: false, detail: "2 of 10 requirements have no suitable approved test: URS-004, URS-005." },
      { key: "deviations", label: "No open deviations", passed: true, detail: "All deviations are closed or accepted." },
    ],
  };

  it("explains each open check in words", () => {
    render(<GateChecklist gate={gate} />);
    expect(screen.getByText(/1 of 2 checks met/)).toBeInTheDocument();
    expect(screen.getByText(/URS-004, URS-005/)).toBeInTheDocument();
    expect(screen.getByLabelText("Open")).toBeInTheDocument();
    expect(screen.getByLabelText("Met")).toBeInTheDocument();
  });
});

describe("LifecycleStepper", () => {
  it("marks the current stage", () => {
    render(<LifecycleStepper stage="testing" />);
    expect(screen.getByText("Testing").closest("li")).toHaveAttribute("aria-current", "step");
    expect(screen.getByText("Requirements").closest("li")).toHaveClass("done");
  });
});

describe("SignatureModal", () => {
  it("shows who signs and what it means, and needs the password", async () => {
    const onSign = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();
    render(<SignatureModal title="Approve" meaning="Approved" record="CR-0001: Upgrade" onSign={onSign} onClose={onClose} />);
    expect(screen.getByText("Approved")).toBeInTheDocument();
    expect(screen.getByText(/Signing as Eva Mayr \(QA manager\)/)).toBeInTheDocument();
    const submit = screen.getByRole("button", { name: /Sign/ });
    expect(submit).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Password"), "secret-password");
    await userEvent.type(screen.getByLabelText(/Comment/), "Looks good");
    expect(submit).toBeEnabled();
    await userEvent.click(submit);
    await waitFor(() => expect(onSign).toHaveBeenCalledWith("secret-password", "Looks good"));
    expect(onClose).toHaveBeenCalled();
  });

  it("stays open and shows the error when the signature is refused", async () => {
    const onSign = vi.fn().mockRejectedValue(new Error("The password is not correct."));
    const onClose = vi.fn();
    render(<SignatureModal title="Approve" meaning="Approved" record="CR-0001" onSign={onSign} onClose={onClose} />);
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /Sign/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The password is not correct.");
    expect(onClose).not.toHaveBeenCalled();
  });
});
