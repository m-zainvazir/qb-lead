"use client";

import { useState, useTransition } from "react";

import { finishOnboarding, saveProgress, type Answers } from "./actions";

export type Question = {
  key: string;
  step: number;
  type:
    | "single_choice"
    | "multi_choice"
    | "number"
    | "text"
    | "long_text"
    | "catalogue_services"
    | "catalogue_markets"
    | "catalogue_signals";
  label: string;
  help: string;
  options: { value: string; label: string }[];
  required: boolean;
  validation: {
    min?: number;
    max?: number;
    min_items?: number;
    max_items?: number;
    max_length?: number;
  };
  show_if: { question: string; equals: string } | null;
};

export type CatalogueOption = {
  id: string;
  label: string;
  description?: string;
  temperature?: string;
};

function visible(q: Question, answers: Answers) {
  return !q.show_if || answers[q.show_if.question] === q.show_if.equals;
}

function problem(q: Question, value: Answers[string]): string | null {
  const v = q.validation;
  const empty =
    value === undefined ||
    value === null ||
    value === "" ||
    (Array.isArray(value) && value.length === 0);
  if (empty) return q.required ? "Please answer this question." : null;
  if (Array.isArray(value)) {
    if (v.min_items && value.length < v.min_items) return `Choose at least ${v.min_items}.`;
    if (v.max_items && value.length > v.max_items) return `Choose at most ${v.max_items}.`;
  }
  if (q.type === "number") {
    const n = Number(value);
    if (!Number.isFinite(n)) return "Enter a number.";
    if (v.min !== undefined && n < v.min) return `The smallest allowed value is ${v.min}.`;
    if (v.max !== undefined && n > v.max) return `The largest allowed value is ${v.max}.`;
  }
  if (typeof value === "string" && v.max_length && value.length > v.max_length) {
    return `Keep it under ${v.max_length} characters.`;
  }
  return null;
}

export function Wizard({
  tenantId,
  questions,
  options,
  steps,
  initialStep,
  initialAnswers,
}: {
  tenantId: string;
  questions: Question[];
  options: Record<string, CatalogueOption[]>;
  steps: number;
  initialStep: number;
  initialAnswers: Answers;
}) {
  const [step, setStep] = useState(Math.min(Math.max(initialStep, 1), steps));
  const [answers, setAnswers] = useState<Answers>(initialAnswers);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const current = questions.filter((q) => q.step === step && visible(q, answers));
  const set = (key: string, value: Answers[string]) => setAnswers((a) => ({ ...a, [key]: value }));

  function go(next: number, finish = false) {
    if (next > step || finish) {
      const found: Record<string, string> = {};
      for (const q of current) {
        const p = problem(q, answers[q.key]);
        if (p) found[q.key] = p;
      }
      setErrors(found);
      if (Object.keys(found).length) return;
    }
    const kept = Object.fromEntries(
      Object.entries(answers).filter(([k]) => {
        const q = questions.find((x) => x.key === k);
        return q && visible(q, answers);
      }),
    );
    setFormError(null);
    startTransition(async () => {
      const res = finish
        ? await finishOnboarding(tenantId, step, kept)
        : await saveProgress(tenantId, next, kept);
      if (res?.error) setFormError(res.error);
      else if (!finish) setStep(next);
    });
  }

  return (
    <div className="flex max-w-xl flex-col gap-6">
      <p className="text-sm text-neutral-500">
        Step {step} of {steps}. Your answers are saved at every step.
      </p>
      {current.map((q) => (
        <fieldset key={q.key} className="flex flex-col gap-2">
          <legend className="text-sm font-medium">
            {q.label} {!q.required && <span className="text-neutral-400">(optional)</span>}
          </legend>
          {q.help && <p className="text-xs text-neutral-500">{q.help}</p>}
          <Input
            q={q}
            value={answers[q.key]}
            options={options[q.type] ?? q.options.map((o) => ({ id: o.value, label: o.label }))}
            onChange={(v) => set(q.key, v)}
          />
          {errors[q.key] && (
            <p role="alert" className="text-xs text-red-700">
              {errors[q.key]}
            </p>
          )}
        </fieldset>
      ))}
      {formError && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          {formError}
        </p>
      )}
      <div className="flex gap-3">
        {step > 1 && (
          <button
            type="button"
            disabled={pending}
            onClick={() => go(step - 1)}
            className="rounded-md border px-4 py-2 text-sm"
          >
            Back
          </button>
        )}
        {step < steps ? (
          <button
            type="button"
            disabled={pending}
            onClick={() => go(step + 1)}
            className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {pending ? "Saving…" : "Next"}
          </button>
        ) : (
          <button
            type="button"
            disabled={pending}
            onClick={() => go(step, true)}
            className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {pending ? "Saving…" : "Finish"}
          </button>
        )}
      </div>
    </div>
  );
}

function Input({
  q,
  value,
  options,
  onChange,
}: {
  q: Question;
  value: Answers[string];
  options: CatalogueOption[];
  onChange: (v: Answers[string]) => void;
}) {
  const field = "rounded-md border border-neutral-300 px-3 py-2 text-sm";
  switch (q.type) {
    case "number":
      return (
        <input
          type="number"
          className={field}
          value={value === null || value === undefined ? "" : String(value)}
          min={q.validation.min}
          max={q.validation.max}
          onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        />
      );
    case "text":
      return (
        <input
          className={field}
          maxLength={q.validation.max_length}
          value={typeof value === "string" ? value : ""}
          onChange={(e) => onChange(e.target.value)}
        />
      );
    case "long_text":
      return (
        <textarea
          className={field}
          rows={4}
          maxLength={q.validation.max_length}
          value={typeof value === "string" ? value : ""}
          onChange={(e) => onChange(e.target.value)}
        />
      );
    case "single_choice":
      return (
        <div className="flex flex-col gap-1">
          {options.map((o) => (
            <label key={o.id} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name={q.key}
                checked={value === o.id}
                onChange={() => onChange(o.id)}
              />
              {o.label}
            </label>
          ))}
        </div>
      );
    default: {
      const chosen = Array.isArray(value) ? value : [];
      return (
        <div className="flex flex-col gap-1">
          {options.map((o) => (
            <label key={o.id} className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                checked={chosen.includes(o.id)}
                onChange={(e) =>
                  onChange(e.target.checked ? [...chosen, o.id] : chosen.filter((c) => c !== o.id))
                }
              />
              <span>
                {o.label}
                {o.temperature && (
                  <span className="ml-1 text-xs text-neutral-500">({o.temperature})</span>
                )}
                {o.description && (
                  <span className="block text-xs text-neutral-500">{o.description}</span>
                )}
              </span>
            </label>
          ))}
        </div>
      );
    }
  }
}
