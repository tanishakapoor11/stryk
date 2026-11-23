import { CompetitionDirectoryPage } from "@/features/competitions/directory-page";
import type { RawParams } from "@/lib/search-params";

export const metadata = { title: "Competitions" };

export default function Page({ searchParams }: { searchParams: RawParams }) {
  return <CompetitionDirectoryPage preset="all" searchParams={searchParams} />;
}
