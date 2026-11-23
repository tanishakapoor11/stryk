import { CompetitionDirectoryPage } from "@/features/competitions/directory-page";
import type { RawParams } from "@/lib/search-params";

export const metadata = { title: "International cricket" };

export default function Page({ searchParams }: { searchParams: RawParams }) {
  return <CompetitionDirectoryPage preset="international" searchParams={searchParams} />;
}
