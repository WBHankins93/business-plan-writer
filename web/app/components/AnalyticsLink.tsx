"use client";

import type { AnchorHTMLAttributes, MouseEvent, ReactNode } from "react";

type AnalyticsValue = string | number | boolean;
export type AnalyticsEvent = {
  name: "cta_click" | "sample_download" | "account_start";
  properties: Record<string, AnalyticsValue>;
};

declare global {
  interface Window {
    dataLayer?: Array<Record<string, unknown>>;
  }
}

const emitAnalyticsEvent = ({ name, properties }: AnalyticsEvent) => {
  const payload = { event: name, ...properties };

  window.dataLayer?.push(payload);
  window.dispatchEvent(
    new CustomEvent("business-plan-writer:analytics", { detail: payload }),
  );
};

type AnalyticsLinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & {
  children: ReactNode;
  events: AnalyticsEvent[];
};

export function AnalyticsLink({ children, events, onClick, ...props }: AnalyticsLinkProps) {
  const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
    events.forEach(emitAnalyticsEvent);
    onClick?.(event);
  };

  return (
    <a {...props} onClick={handleClick}>
      {children}
    </a>
  );
}
