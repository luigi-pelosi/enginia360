import { getRequestConfig } from "next-intl/server";
import { cookies } from "next/headers";
export default getRequestConfig(async () => {
  const locale = (await cookies()).get("locale")?.value === "en" ? "en" : "it";
  return {
    locale,
    timeZone: "Europe/Rome",
    messages: (await import(`../messages/${locale}.json`)).default,
  };
});
