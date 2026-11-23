import { CompetitionDirectoryPage } from "@/features/competitions/directory-page";
import type { RawParams } from "@/lib/search-params";

export const metadata = { title: "ICC tournaments" };

export default function Page({ searchParams }: { searchParams: RawParams }) {
  return <CompetitionDirectoryPage preset="tournaments" searchParams={searchParams} />;
}
