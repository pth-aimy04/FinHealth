import { useState, type ReactElement } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "./ui/button";
export type Field = {
  name: string;
  label: string;
  type?: "text" | "email" | "password" | "number" | "textarea" | "select";
  required?: boolean;
  min?: number;
  max?: number;
  integer?: boolean;
  pattern?: RegExp;
  options?: { value: string; label: string }[];
  hint?: string;
  defaultValue?: string;
};
/** Schema-validated form retaining inputs after failures and focusing associated inline errors. */
export function DataForm({
  fields,
  submit,
  onSubmit,
  defaults = {},
  compact = false,
}: {
  fields: Field[];
  submit: string;
  onSubmit: (values: Record<string, string>) => Promise<string | void>;
  defaults?: Record<string, string>;
  compact?: boolean;
}): ReactElement {
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const schema = z.record(z.string(), z.string()).superRefine((values, ctx) => {
    fields.forEach((field) => {
      const value = values[field.name] ?? "";
      let message = "";
      if (field.required && !value.trim())
        message = "Vui lòng nhập trường này.";
      else if (
        value &&
        field.type === "email" &&
        !z.email().safeParse(value).success
      )
        message = "Nhập địa chỉ email hợp lệ.";
      else if (value && field.type === "number") {
        const number = Number(value);
        if (
          !Number.isFinite(number) ||
          (field.min !== undefined && number < field.min) ||
          (field.max !== undefined && number > field.max) ||
          (field.integer && !Number.isInteger(number))
        )
          message = `Nhập số hợp lệ${field.min !== undefined ? ` từ ${field.min}` : ""}${field.max !== undefined ? ` đến ${field.max}` : ""}.`;
      } else if (value && field.min !== undefined && value.length < field.min)
        message = `Cần ít nhất ${field.min} ký tự.`;
      else if (value && field.max !== undefined && value.length > field.max)
        message = `Tối đa ${field.max} ký tự.`;
      if (!message && value && field.pattern && !field.pattern.test(value))
        message = "Định dạng chưa hợp lệ.";
      if (message)
        ctx.addIssue({ code: "custom", path: [field.name], message });
    });
  });
  const form = useForm<Record<string, string>>({
    resolver: zodResolver(schema),
    mode: "onBlur",
    defaultValues: Object.fromEntries(
      fields.map((field) => [
        field.name,
        defaults[field.name] ?? field.defaultValue ?? "",
      ]),
    ),
  });
  const errors = form.formState.errors;
  return (
    <form
      className="form-stack"
      noValidate
      onSubmit={form.handleSubmit(async (values) => {
        setError("");
        setStatus("");
        try {
          const message = await onSubmit(values);
          setStatus(message ?? "Đã hoàn tất.");
        } catch (cause) {
          setError(
            cause instanceof Error
              ? cause.message
              : "Yêu cầu không hoàn tất. Hãy thử lại.",
          );
        }
      })}
    >
      <div className={compact ? "form-stack" : "form-grid"}>
        {fields.map((field) => (
          <label key={field.name} htmlFor={`field-${field.name}`}>
            {field.label}
            {field.required ? " *" : ""}
            {field.type === "textarea" ? (
              <textarea
                id={`field-${field.name}`}
                {...form.register(field.name)}
                aria-invalid={Boolean(errors[field.name])}
                aria-describedby={`hint-${field.name} error-${field.name}`}
              />
            ) : field.type === "select" ? (
              <select
                id={`field-${field.name}`}
                {...form.register(field.name)}
                aria-describedby={`hint-${field.name} error-${field.name}`}
              >
                {field.options?.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                id={`field-${field.name}`}
                type={field.type ?? "text"}
                step={field.integer ? 1 : "any"}
                {...form.register(field.name)}
                aria-required={field.required}
                aria-invalid={Boolean(errors[field.name])}
                aria-describedby={`hint-${field.name} error-${field.name}`}
                autoComplete={
                  field.type === "password"
                    ? field.name.includes("new")
                      ? "new-password"
                      : "current-password"
                    : field.type === "email"
                      ? "email"
                      : field.name === "code"
                        ? "one-time-code"
                        : "off"
                }
                inputMode={field.name === "code" ? "numeric" : undefined}
                maxLength={field.type === "number" ? undefined : field.max}
              />
            )}
            {field.hint && (
              <span id={`hint-${field.name}`} className="small muted">
                {field.hint}
              </span>
            )}
            <span id={`error-${field.name}`} className="field-error">
              {errors[field.name]?.message}
            </span>
          </label>
        ))}
      </div>
      {error && (
        <p role="alert" className="field-error">
          {error}
        </p>
      )}
      {status && (
        <p role="status" className="positive form-status">
          {status}
        </p>
      )}
      <Button type="submit" disabled={form.formState.isSubmitting}>
        {form.formState.isSubmitting ? "Đang xử lý…" : submit}
      </Button>
    </form>
  );
}
