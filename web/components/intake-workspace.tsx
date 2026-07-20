"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import { API_BASE_URL, authenticatedFetch, SessionExpiredError } from "../lib/api";
import { DEMO_INTAKE } from "../lib/demo-intake";
import { createClient } from "../lib/supabase/client";

type Tier = 1 | 2 | 3;
type IntakeValues = Record<string, Record<string, string>>;
type FieldErrors = Record<string, string>;
type FieldIssue = { field: string; message?: string } | string;
type Question = {
  section: string;
  name: string;
  label: string;
  prompt: string;
  tier: Tier;
  multiline?: boolean;
  placeholder?: string;
};
type IntakeStep = {
  title: string;
  shortTitle: string;
  intro: string;
  questions: Question[];
};
type StepState = { step: number; name: string; status: string };
type ValidationWarnings = {
  missing_required: FieldIssue[];
  thin_fields: FieldIssue[];
  completeness_score?: number;
};
type CriticOutput = {
  scores?: Record<string, number>;
  primary_risks?: string[];
  approval_status?: string;
};
type GenerateResult = {
  progress?: StepState[];
  draft_markdown?: string;
  validation_warnings?: ValidationWarnings;
  critic?: CriticOutput;
  exports?: { docx: string | null; pdf: string | null };
};
type RunResponse = {
  run_id: string;
  client_slug: string;
  status: string;
  progress?: StepState[];
  error?: { code?: string; message?: string } | null;
  result?: GenerateResult | null;
};
type ApiErrorDetail = {
  message?: string;
  fields?: Array<{ field?: string; message?: string }>;
};

const STEP_NAMES = ["Validation", "Market", "Financials", "Draft", "Review"];
const REVIEW_STEP_INDEX = 4;

const INTAKE_STEPS: IntakeStep[] = [
  {
    title: "Your business",
    shortTitle: "Business",
    intro: "Start with the facts that anchor the plan and the people responsible for it.",
    questions: [
      { section: "business_information", name: "business_name", label: "Business name", prompt: "What name should appear on the plan?", tier: 1, placeholder: "Northstar Home Care Advisors" },
      { section: "business_information", name: "owner_name", label: "Primary owner", prompt: "Who is the primary owner or founder?", tier: 1, placeholder: "Jordan Lee" },
      { section: "business_information", name: "ownership_structure", label: "Ownership structure", prompt: "How is the business legally organized?", tier: 1, placeholder: "LLC, sole proprietorship, S corporation…" },
      { section: "business_information", name: "industry", label: "Industry", prompt: "What industry or sector best describes the business?", tier: 1, placeholder: "Eldercare planning and family advisory services" },
      { section: "business_information", name: "business_stage", label: "Current stage", prompt: "Where is the business today?", tier: 2, placeholder: "Operating, expanding, opening a new location…" },
      { section: "business_information", name: "funding_purpose", label: "Purpose of this plan", prompt: "What decision or funding request should this plan support?", tier: 2, multiline: true },
      { section: "business_information", name: "funding_amount", label: "Funding amount", prompt: "How much funding is being sought, if any?", tier: 2, placeholder: "$85,000" },
      { section: "business_information", name: "location", label: "Business location", prompt: "Where will the business operate and serve customers?", tier: 2, placeholder: "Chicago, Illinois and surrounding suburbs" },
      { section: "business_information", name: "year_founded", label: "Year founded", prompt: "When was or will the business be founded?", tier: 3, placeholder: "2026" },
      { section: "management_details", name: "owner_background", label: "Owner experience", prompt: "What experience and credentials prepare the owner to run this business?", tier: 1, multiline: true },
      { section: "management_details", name: "management_team", label: "Management team", prompt: "Who else will lead the business, and what will they own?", tier: 2, multiline: true },
      { section: "management_details", name: "hiring_plans", label: "Hiring plan", prompt: "Which roles will be hired, and when?", tier: 2, multiline: true },
      { section: "management_details", name: "advisors", label: "Advisors or board", prompt: "Which advisors, mentors, or board members support the business?", tier: 3, multiline: true },
    ],
  },
  {
    title: "Offer and market",
    shortTitle: "Market",
    intro: "Describe what customers buy, who needs it, and the alternatives they consider.",
    questions: [
      { section: "product_service_summary", name: "services_offered", label: "Products or services", prompt: "What does the business sell or provide?", tier: 1, multiline: true },
      { section: "product_service_summary", name: "service_delivery", label: "How it is delivered", prompt: "How will customers receive the product or service?", tier: 2, multiline: true },
      { section: "product_service_summary", name: "pricing_structure", label: "Pricing", prompt: "How will customers be charged?", tier: 2, multiline: true },
      { section: "product_service_summary", name: "differentiators", label: "What makes it different", prompt: "Why would a customer choose this offer over an alternative?", tier: 2, multiline: true },
      { section: "product_service_summary", name: "future_offerings", label: "Future offers", prompt: "What might be added later?", tier: 3, multiline: true },
      { section: "market_analysis", name: "geographic_market", label: "Geographic market", prompt: "Where are the customers the business will serve?", tier: 1, multiline: true },
      { section: "market_analysis", name: "target_customer", label: "Ideal customer", prompt: "Who is the primary customer, and what situation are they in?", tier: 1, multiline: true },
      { section: "market_analysis", name: "market_size", label: "Market opportunity", prompt: "What is known about the size or demand of the reachable market?", tier: 2, multiline: true },
      { section: "market_analysis", name: "industry_state", label: "Industry outlook", prompt: "Which trends or changes are shaping this industry?", tier: 2, multiline: true },
      { section: "market_analysis", name: "customer_pain_points", label: "Customer problems", prompt: "What important problems does the customer need solved?", tier: 2, multiline: true },
      { section: "competition", name: "main_competitors", label: "Main competitors", prompt: "Which companies or types of alternatives compete for this customer?", tier: 1, multiline: true },
      { section: "competition", name: "competitive_edge", label: "Competitive advantage", prompt: "What defensible reason will customers choose this business?", tier: 1, multiline: true },
      { section: "competition", name: "market_gaps", label: "Unmet market needs", prompt: "Which customer needs are not being served well today?", tier: 2, multiline: true },
    ],
  },
  {
    title: "Growth plan",
    shortTitle: "Growth",
    intro: "Connect customer acquisition to the actions, milestones, and risks that drive execution.",
    questions: [
      { section: "sales_strategy", name: "sales_process", label: "Sales process", prompt: "How does a prospect become a paying customer?", tier: 2, multiline: true },
      { section: "sales_strategy", name: "payment_terms", label: "Payment terms", prompt: "When and how will customers pay?", tier: 2, multiline: true },
      { section: "sales_strategy", name: "retention_strategy", label: "Customer retention", prompt: "How will the business encourage repeat business or renewals?", tier: 2, multiline: true },
      { section: "sales_strategy", name: "referral_sources", label: "Lead and referral sources", prompt: "Which people or channels will produce qualified leads?", tier: 2, multiline: true },
      { section: "advertising_strategy", name: "initial_marketing", label: "First marketing channels", prompt: "How will the business reach its first customers?", tier: 1, multiline: true },
      { section: "advertising_strategy", name: "marketing_budget", label: "Marketing budget", prompt: "What monthly or annual marketing budget is planned?", tier: 2, placeholder: "$3,500 per month" },
      { section: "advertising_strategy", name: "digital_presence", label: "Digital presence", prompt: "What role will the website, search, email, or online channels play?", tier: 2, multiline: true },
      { section: "advertising_strategy", name: "expansion_marketing", label: "Later-stage marketing", prompt: "How will marketing change as the business grows?", tier: 3, multiline: true },
      { section: "strategy_and_implementation", name: "business_strategy", label: "Business strategy", prompt: "What is the overall approach to building and growing the business?", tier: 1, multiline: true },
      { section: "strategy_and_implementation", name: "near_term_priorities", label: "Next 90 days", prompt: "What are the three to five most important near-term priorities?", tier: 2, multiline: true },
      { section: "strategy_and_implementation", name: "key_risks", label: "Key risks and responses", prompt: "What could derail the plan, and how will each risk be managed?", tier: 2, multiline: true },
      { section: "strategy_and_implementation", name: "partnerships", label: "Key partnerships", prompt: "Which partners, vendors, or relationships are important to execution?", tier: 3, multiline: true },
      { section: "milestones", name: "twelve_month_goals", label: "12-month goals", prompt: "What specific results should be reached in the first year?", tier: 1, multiline: true },
      { section: "milestones", name: "twenty_four_month_goals", label: "24-month goals", prompt: "What should be true by the end of year two?", tier: 2, multiline: true },
      { section: "milestones", name: "key_metrics", label: "Measures of success", prompt: "Which numbers will show whether the plan is working?", tier: 2, multiline: true },
    ],
  },
  {
    title: "Financial picture",
    shortTitle: "Financials",
    intro: "Use realistic numbers and explain the assumptions behind them. Estimates are welcome.",
    questions: [
      { section: "financial_information", name: "cash_flow_narrative", label: "Cash flow story", prompt: "How will cash enter and leave the business as it ramps?", tier: 1, multiline: true },
      { section: "financial_information", name: "financial_plan_summary", label: "Financial plan", prompt: "What are the main financial assumptions and sources of capital?", tier: 1, multiline: true },
      { section: "financial_information", name: "break_even_point", label: "Break-even target", prompt: "When and at what revenue level should the business break even?", tier: 2, multiline: true },
      { section: "income", name: "beginning_balance", label: "Starting capital", prompt: "How much cash or capital is available at launch?", tier: 1, placeholder: "$50,000" },
      { section: "income", name: "client_volume", label: "Customer volume", prompt: "How many customers or transactions are expected by month or phase?", tier: 1, multiline: true },
      { section: "income", name: "monthly_revenue_projection", label: "Monthly revenue", prompt: "What monthly revenue is projected? Include a number or month-by-month schedule.", tier: 1, multiline: true, placeholder: "$20,000 per month, or Month 1: $8,000; Month 2: $10,000…" },
      { section: "income", name: "annual_revenue_projection", label: "Annual revenue", prompt: "What are the projected annual revenue totals?", tier: 2, multiline: true, placeholder: "Year 1: $240,000; Year 2: $420,000" },
      { section: "income", name: "revenue_sources", label: "Revenue mix", prompt: "How is revenue divided across products, services, or channels?", tier: 2, multiline: true },
      { section: "expenses", name: "payroll", label: "Payroll and contractors", prompt: "What will the business spend on owners, employees, and contractors?", tier: 2, multiline: true },
      { section: "expenses", name: "rent_utilities", label: "Rent and utilities", prompt: "What are the expected workspace and utility costs?", tier: 2, multiline: true },
      { section: "expenses", name: "cogs", label: "Direct costs", prompt: "Which costs rise directly with each sale or service delivered?", tier: 2, multiline: true },
      { section: "expenses", name: "advertising_expense", label: "Advertising expense", prompt: "How much will be spent on advertising and promotion?", tier: 2, multiline: true },
      { section: "expenses", name: "other_operating", label: "Other operating costs", prompt: "What will software, insurance, licenses, supplies, and professional services cost?", tier: 2, multiline: true },
      { section: "expenses", name: "taxes", label: "Taxes", prompt: "What tax obligations are included in the forecast?", tier: 2, multiline: true },
      { section: "expenses", name: "loans_debt_service", label: "Loan payments", prompt: "What loan or financing payments are expected?", tier: 3, multiline: true },
      { section: "expenses", name: "capital_assets", label: "Equipment and assets", prompt: "Which one-time equipment or asset purchases are planned?", tier: 3, multiline: true },
    ],
  },
];

const ALL_QUESTIONS = INTAKE_STEPS.flatMap((step) => step.questions);
const QUESTION_BY_PATH = Object.fromEntries(
  ALL_QUESTIONS.map((question) => [`${question.section}.${question.name}`, question])
) as Record<string, Question>;
const NUMERIC_FIELDS = new Set([
  "business_information.funding_amount",
  "advertising_strategy.marketing_budget",
  "income.beginning_balance",
  "income.monthly_revenue_projection",
  "income.annual_revenue_projection",
  "expenses.payroll",
  "expenses.rent_utilities",
  "expenses.advertising_expense",
  "expenses.taxes",
]);

const fieldPath = (question: Question) => `${question.section}.${question.name}`;
const emptyIntake = (): IntakeValues => {
  const values: IntakeValues = {};
  for (const question of ALL_QUESTIONS) {
    values[question.section] ||= {};
    values[question.section][question.name] = "";
  }
  return values;
};

const canonicalIntake = (source: unknown): IntakeValues => {
  const values = emptyIntake();
  if (!source || typeof source !== "object") return values;
  const input = source as Record<string, unknown>;
  for (const question of ALL_QUESTIONS) {
    const section = input[question.section];
    if (!section || typeof section !== "object") continue;
    const raw = (section as Record<string, unknown>)[question.name];
    values[question.section][question.name] = raw == null ? "" : String(raw);
  }
  return values;
};

const statusSteps = (status: string) =>
  STEP_NAMES.map((name, index) => ({ step: index + 1, name, status }));

const artifactUrl = (path: string | null) => {
  if (!path) return null;
  return path.startsWith("http") ? path : `${API_BASE_URL}${path}`;
};

const validateFields = (values: IntakeValues, questions: Question[]): FieldErrors => {
  const errors: FieldErrors = {};
  for (const question of questions) {
    const path = fieldPath(question);
    const value = values[question.section]?.[question.name]?.trim() || "";
    if (question.tier === 1 && !value) {
      errors[path] = `${question.label} is required.`;
    } else if (value && NUMERIC_FIELDS.has(path) && !/\d/.test(value)) {
      errors[path] = `${question.label} must include a number.`;
    }
  }
  return errors;
};

const tierLabel = (tier: Tier) => (tier === 1 ? "Required" : tier === 2 ? "Follow-up" : "Optional");

const readableIssue = (item: FieldIssue) => {
  const path = typeof item === "string" ? item : item.field;
  return QUESTION_BY_PATH[path]?.label || path.replaceAll("_", " ");
};

export function IntakeWorkspace({ projectId, demoMode = false }: { projectId?: string; demoMode?: boolean }) {
  const router = useRouter();
  const supabase = useMemo(() => demoMode ? null : createClient(), [demoMode]);
  const [intake, setIntake] = useState<IntakeValues>(emptyIntake);
  const [activeStep, setActiveStep] = useState(0);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [steps, setSteps] = useState<StepState[]>([]);
  const [draft, setDraft] = useState("");
  const [warnings, setWarnings] = useState<ValidationWarnings>({ missing_required: [], thin_fields: [] });
  const [critic, setCritic] = useState<CriticOutput>({});
  const [exports, setExports] = useState<{ docx: string | null; pdf: string | null }>({ docx: null, pdf: null });
  const [runState, setRunState] = useState<"idle" | "queueing" | "running">("idle");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [runId, setRunId] = useState("");
  const [loaded, setLoaded] = useState(demoMode);
  const [accountEmail, setAccountEmail] = useState("");
  const [saveState, setSaveState] = useState<"saved" | "pending" | "saving" | "error">("saved");
  const [saveError, setSaveError] = useState("");
  const lastSavedSnapshot = useRef("");
  const latestSnapshot = useRef("");
  const saveRequest = useRef(0);
  const saveQueue = useRef<Promise<boolean>>(Promise.resolve(true));

  const answeredRequired = useMemo(
    () => ALL_QUESTIONS.filter((question) => question.tier === 1 && intake[question.section]?.[question.name]?.trim()).length,
    [intake]
  );
  const requiredCount = ALL_QUESTIONS.filter((question) => question.tier === 1).length;
  const isBusy = runState !== "idle";

  const snapshot = JSON.stringify({ intake: canonicalIntake(intake), current_step: activeStep });
  latestSnapshot.current = snapshot;

  const sessionExpired = () => {
    const next = projectId ? `/projects/${projectId}` : "/projects";
    router.replace(`/login?next=${encodeURIComponent(next)}`);
    router.refresh();
  };

  const privateFetch = async (path: string, init?: RequestInit) => {
    if (!supabase) throw new Error("Authentication is not available in demo mode.");
    try {
      return await authenticatedFetch(supabase, path, init);
    } catch (caught) {
      if (caught instanceof SessionExpiredError) sessionExpired();
      throw caught;
    }
  };

  const persistDraft = async (
    values: IntakeValues = intake,
    step: number = activeStep
  ): Promise<boolean> => {
    if (demoMode || !projectId) return true;
    const requestedSnapshot = JSON.stringify({ intake: canonicalIntake(values), current_step: step });
    const requestNumber = ++saveRequest.current;
    setSaveError("");
    const operation = saveQueue.current.then(async () => {
      if (requestNumber === saveRequest.current) setSaveState("saving");
      try {
        const response = await privateFetch(`/projects/${projectId}/draft`, {
          method: "PUT",
          body: JSON.stringify({ intake: canonicalIntake(values), current_step: step }),
        });
        if (!response.ok) throw new Error("Your latest changes could not be saved.");
        lastSavedSnapshot.current = requestedSnapshot;
        if (requestNumber === saveRequest.current) {
          setSaveState(latestSnapshot.current === requestedSnapshot ? "saved" : "pending");
        }
        return true;
      } catch (caught) {
        if (requestNumber === saveRequest.current) {
          setSaveState("error");
          setSaveError(caught instanceof SessionExpiredError ? "Your session expired before these changes could be saved." : "Changes are still on this page. Retry saving before you leave or refresh.");
        }
        return false;
      }
    });
    saveQueue.current = operation;
    return operation;
  };

  useEffect(() => {
    if (demoMode || !projectId) return;
    let cancelled = false;
    const loadProject = async () => {
      setLoaded(false);
      setError("");
      try {
        const [{ data: userData }, response] = await Promise.all([
          supabase!.auth.getUser(),
          privateFetch(`/projects/${projectId}`),
        ]);
        if (!response.ok) throw new Error(response.status === 404 ? "This project was not found." : "This saved intake could not be loaded.");
        const project = await response.json();
        if (cancelled) return;
        const restored = canonicalIntake(project.intake);
        const restoredStep = Math.max(0, Math.min(Number(project.current_step) || 0, REVIEW_STEP_INDEX));
        lastSavedSnapshot.current = JSON.stringify({ intake: restored, current_step: restoredStep });
        setIntake(restored);
        setActiveStep(restoredStep);
        setAccountEmail(userData.user?.email || "Signed in");
        setSaveState("saved");
        setLoaded(true);
      } catch (caught) {
        if (cancelled || caught instanceof SessionExpiredError) return;
        setError(caught instanceof Error ? caught.message : "This saved intake could not be loaded.");
        setLoaded(true);
      }
    };
    void loadProject();
    return () => { cancelled = true; };
  }, [demoMode, projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (demoMode || !projectId || !loaded || snapshot === lastSavedSnapshot.current) return;
    setSaveState("pending");
    const timer = window.setTimeout(() => { void persistDraft(intake, activeStep); }, 900);
    return () => window.clearTimeout(timer);
  }, [snapshot, loaded, demoMode, projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const updateField = (question: Question, value: string) => {
    const path = fieldPath(question);
    setIntake((previous) => ({
      ...previous,
      [question.section]: { ...previous[question.section], [question.name]: value },
    }));
    if (fieldErrors[path]) {
      setFieldErrors((previous) => {
        const next = { ...previous };
        delete next[path];
        return next;
      });
    }
  };

  const moveToStep = (nextStep: number) => {
    if (nextStep > activeStep && activeStep < INTAKE_STEPS.length) {
      const errors = validateFields(intake, INTAKE_STEPS[activeStep].questions);
      if (Object.keys(errors).length) {
        setFieldErrors((previous) => ({ ...previous, ...errors }));
        setError("Complete the required questions in this step before continuing.");
        window.setTimeout(() => document.getElementById("form-error-summary")?.focus(), 0);
        return;
      }
    }
    setError("");
    setActiveStep(nextStep);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const loadDemo = () => {
    setError("");
    const demo = canonicalIntake(DEMO_INTAKE);
    setIntake(demo);
    setFieldErrors({});
    setDraft("");
    setWarnings({ missing_required: [], thin_fields: [] });
    setCritic({});
    setExports({ docx: null, pdf: null });
    setRunId("");
    setSteps([]);
    setActiveStep(REVIEW_STEP_INDEX);
    setNotice("Demo intake loaded. Review the answers, then generate the plan.");
  };

  const pollRun = async (id: string): Promise<RunResponse> => {
    for (let attempt = 0; attempt < 180; attempt += 1) {
      const response = demoMode
        ? await fetch(`${API_BASE_URL}/demo/runs/${id}`)
        : await privateFetch(`/runs/${id}`);
      const data = (await response.json()) as RunResponse;
      if (!response.ok) throw new Error("The queued run could not be checked. Try again in a moment.");
      setSteps(data.progress || []);
      if (data.status === "succeeded") return data;
      if (data.status === "failed") {
        throw new Error(data.error?.message || "The pipeline could not finish this plan. Review the server run details.");
      }
      await new Promise((resolve) => window.setTimeout(resolve, 2000));
    }
    throw new Error("Plan generation took longer than expected. The run may still be processing.");
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const errors = validateFields(intake, ALL_QUESTIONS);
    if (Object.keys(errors).length) {
      setFieldErrors(errors);
      const firstPath = Object.keys(errors)[0];
      const firstStep = INTAKE_STEPS.findIndex((step) => step.questions.some((question) => fieldPath(question) === firstPath));
      setActiveStep(Math.max(firstStep, 0));
      setError(`Review ${Object.keys(errors).length} highlighted field${Object.keys(errors).length === 1 ? "" : "s"} before generating the plan.`);
      window.setTimeout(() => document.getElementById("form-error-summary")?.focus(), 0);
      return;
    }

    setRunState("queueing");
    setError("");
    setNotice("Starting the plan checks and first draft…");
    setSteps(statusSteps("queued"));
    setDraft("");

    try {
      if (!demoMode && !(await persistDraft(intake, activeStep))) {
        throw new Error("Save the latest changes before starting generation.");
      }
      const response = demoMode
        ? await fetch(`${API_BASE_URL}/demo/generate-plan`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ intake: canonicalIntake(intake) }),
          })
        : await privateFetch(`/projects/${projectId}/generate-plan`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) {
        const detail = (data?.detail || {}) as ApiErrorDetail;
        const apiFieldErrors = Object.fromEntries(
          (detail.fields || []).flatMap((item) => item.field && item.message ? [[item.field, item.message]] : [])
        );
        if (Object.keys(apiFieldErrors).length) setFieldErrors(apiFieldErrors);
        throw new Error(detail.message || "The intake could not be queued. Review the form and try again.");
      }

      const queued = data as RunResponse;
      setRunId(queued.run_id);
      setSteps(queued.progress || []);
      setRunState("running");
      setNotice("Plan queued. The agents are now validating, analyzing, drafting, and reviewing it.");

      const finalRun = await pollRun(queued.run_id);
      const result = finalRun.result;
      if (!result) throw new Error("The run finished without a result. Check the run details and try again.");
      setSteps(result.progress || finalRun.progress || []);
      setDraft(result.draft_markdown || "");
      setWarnings(result.validation_warnings || { missing_required: [], thin_fields: [] });
      setCritic(result.critic || {});
      setExports(result.exports || { docx: null, pdf: null });
      setNotice("Plan generated. Review the draft and validation notes below.");
    } catch (caught: unknown) {
      setNotice("");
      setError(caught instanceof Error ? caught.message : "The plan could not be generated.");
      setSteps((previous) => previous.map((step) => ({ ...step, status: "failed" })));
    } finally {
      setRunState("idle");
    }
  };

  const renderQuestion = (question: Question) => {
    const path = fieldPath(question);
    const inputId = `field-${question.section}-${question.name}`;
    const errorId = `${inputId}-error`;
    const hintId = `${inputId}-hint`;
    const value = intake[question.section]?.[question.name] || "";
    const inputProps = {
      id: inputId,
      value,
      placeholder: question.placeholder,
      onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => updateField(question, event.target.value),
      "aria-invalid": Boolean(fieldErrors[path]),
      "aria-describedby": `${hintId}${fieldErrors[path] ? ` ${errorId}` : ""}`,
    };

    return (
      <div className="question" key={path} data-field-path={path}>
        <div className="questionHeading">
          <label htmlFor={inputId}>{question.label}</label>
          <span className={`requirement tier${question.tier}`}>{tierLabel(question.tier)}</span>
        </div>
        <p className="fieldHint" id={hintId}>{question.prompt}</p>
        {question.multiline ? <textarea {...inputProps} rows={4} /> : <input {...inputProps} />}
        {question.tier > 1 && !NUMERIC_FIELDS.has(path) && value !== "I don’t know yet" && (
          <button className="unknownButton" type="button" onClick={() => updateField(question, "I don’t know yet")}>I don’t know yet</button>
        )}
        {fieldErrors[path] && <p className="fieldError" id={errorId}>{fieldErrors[path]}</p>}
      </div>
    );
  };

  const downloadArtifact = async (path: string) => {
    setError("");
    try {
      if (demoMode) {
        window.location.assign(artifactUrl(path) || path);
        return;
      }
      const response = await privateFetch(path);
      if (!response.ok) throw new Error("The export could not be downloaded. Try again.");
      const blobUrl = URL.createObjectURL(await response.blob());
      const disposition = response.headers.get("content-disposition") || "";
      const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] || "business-plan-export";
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(blobUrl);
    } catch (caught) {
      if (!(caught instanceof SessionExpiredError)) {
        setError(caught instanceof Error ? caught.message : "The export could not be downloaded.");
      }
    }
  };

  const visibleStep = INTAKE_STEPS[activeStep];
  const progress = steps.length ? steps : statusSteps("waiting");

  if (!loaded) {
    return <main className="workspace"><p className="notice" role="status">Loading your saved intake…</p></main>;
  }

  return (
    <main className="workspace">
      {!demoMode && (
        <div className="accountBar">
          <Link href="/projects">← All projects</Link>
          <div className={`saveStatus ${saveState}`} aria-live="polite">
            {saveState === "saved" ? "Saved" : saveState === "saving" ? "Saving…" : saveState === "pending" ? "Unsaved changes" : "Save failed"}
            {saveState === "error" && <button type="button" onClick={() => void persistDraft()}>Retry save</button>}
          </div>
          <span>{accountEmail}</span>
          <form action="/auth/signout" method="post"><button className="secondary" type="submit">Log out</button></form>
        </div>
      )}
      {saveError && <div className="saveError" role="alert">{saveError}</div>}
      <header className="hero">
        <div>
          <p className="eyebrow">Structured intake · Human-reviewed delivery</p>
          <h1>Build the case for your business.</h1>
          <p className="heroCopy">Answer one focused set of questions at a time. Your evidence and estimates become a plan you can review, refine, and export.</p>
        </div>
        {demoMode && <button className="demoButton" type="button" onClick={loadDemo} disabled={isBusy}>Load example answers</button>}
      </header>

      <nav className="intakeNav" aria-label="Intake steps">
        {[...INTAKE_STEPS.map((step) => step.shortTitle), "Review"].map((label, index) => (
          <button className={index === activeStep ? "active" : ""} type="button" key={label} onClick={() => moveToStep(index)} aria-current={index === activeStep ? "step" : undefined}>
            <span>{index + 1}</span>{label}
          </button>
        ))}
      </nav>

      <div className="layout">
        <section className="formPanel" aria-labelledby="step-title">
          <form onSubmit={onSubmit} noValidate>
            {error && <div className="errorSummary" id="form-error-summary" role="alert" tabIndex={-1}>{error}</div>}
            {notice && <p className="notice" role="status" aria-live="polite">{notice}</p>}

            {visibleStep ? (
              <>
                <div className="sectionIntro">
                  <p>Step {activeStep + 1} of 5</p>
                  <h2 id="step-title">{visibleStep.title}</h2>
                  <span>{visibleStep.intro}</span>
                </div>
                <div className="questionList">{visibleStep.questions.map(renderQuestion)}</div>
              </>
            ) : (
              <div className="reviewStep">
                <div className="sectionIntro">
                  <p>Step 5 of 5</p>
                  <h2 id="step-title">Review and create your draft</h2>
                  <span>Your required answers are ready. You can return to any section before creating the draft.</span>
                </div>
                <div className="reviewGrid">
                  {INTAKE_STEPS.map((step, index) => {
                    const answered = step.questions.filter((question) => intake[question.section]?.[question.name]?.trim()).length;
                    return (
                      <button type="button" key={step.title} onClick={() => moveToStep(index)}>
                        <span>{step.title}</span><strong>{answered}/{step.questions.length} answered</strong>
                      </button>
                    );
                  })}
                </div>
                <div className="generateCallout">
                  <p><strong>{answeredRequired} of {requiredCount}</strong> required answers complete</p>
                  <p>The service checks completeness, market logic, financial consistency, and draft quality before the result appears here.</p>
                </div>
              </div>
            )}

            <div className="formActions">
              <button className="secondary" type="button" disabled={activeStep === 0 || isBusy} onClick={() => moveToStep(activeStep - 1)}>Back</button>
              {activeStep < REVIEW_STEP_INDEX ? (
                <button type="button" onClick={() => moveToStep(activeStep + 1)}>Continue</button>
              ) : (
                <button type="submit" disabled={isBusy} aria-busy={isBusy}>{runState === "queueing" ? "Starting…" : runState === "running" ? "Creating your draft…" : "Create business plan draft"}</button>
              )}
            </div>
          </form>
        </section>

        <aside className="agentPanel" aria-labelledby="agent-heading">
          <div className="agentHeader">
            <p className="eyebrow">Draft progress</p>
            <h2 id="agent-heading">Plan quality checks</h2>
          </div>
          <ol className="agentRail" aria-live="polite" aria-busy={isBusy}>
            {progress.map((step) => (
              <li key={step.step} data-status={step.status}>
                <span className="agentNumber">{step.step}</span>
                <div><strong>{step.name}</strong><small>{step.status}</small></div>
              </li>
            ))}
          </ol>
          <div className="requiredProgress">
            <div><span>Required intake</span><strong>{answeredRequired}/{requiredCount}</strong></div>
            <progress max={requiredCount} value={answeredRequired}>{answeredRequired} of {requiredCount}</progress>
          </div>
          {runId && <p className="runId">Run <code>{runId}</code></p>}
          <p className="finePrint">This screen shows an AI-assisted draft. Ben reviews and edits accepted customer plans before delivery. Optional answers improve specificity but do not block the draft.</p>
        </aside>
      </div>

      {(draft || warnings.missing_required.length || warnings.thin_fields.length) && (
        <section className="results" aria-labelledby="draft-heading">
          <div className="resultHeader">
            <div>
              <p className="eyebrow">Generated result</p>
              <h2 id="draft-heading">Draft for your review</h2>
              <p>Completeness {warnings.completeness_score ?? "—"}/100 · Review {critic.approval_status || "pending"}</p>
            </div>
            <div className="exportRow">
              {exports.docx && <button className="buttonLink secondary" type="button" onClick={() => void downloadArtifact(exports.docx!)}>Export DOCX</button>}
              {exports.pdf && <button className="buttonLink secondary" type="button" onClick={() => void downloadArtifact(exports.pdf!)}>Export PDF</button>}
            </div>
          </div>
          {(warnings.missing_required.length > 0 || warnings.thin_fields.length > 0 || (critic.primary_risks || []).length > 0) && (
            <div className="reviewNotes">
              <h3>Review notes</h3>
              <ul>
                {warnings.missing_required.slice(0, 4).map((item, index) => <li key={`missing-${index}`}>Missing: {readableIssue(item)}</li>)}
                {warnings.thin_fields.slice(0, 4).map((item, index) => <li key={`thin-${index}`}>Needs detail: {readableIssue(item)}</li>)}
                {(critic.primary_risks || []).slice(0, 4).map((risk, index) => <li key={`risk-${index}`}>Risk: {risk}</li>)}
              </ul>
            </div>
          )}
          <article className="preview"><ReactMarkdown>{draft}</ReactMarkdown></article>
        </section>
      )}
    </main>
  );
}
