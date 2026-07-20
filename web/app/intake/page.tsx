import { redirect } from "next/navigation";

const accountStartUrl = process.env.NEXT_PUBLIC_ACCOUNT_START_URL || "/demo";

export default function IntakeRedirectPage() {
  redirect(accountStartUrl);
}
