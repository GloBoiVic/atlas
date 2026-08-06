import { JournalEntry, listJournalEntries } from "@/lib/api";
import JournalView from "@/app/journal/journal-view";

export const dynamic = "force-dynamic";

export default async function JournalPage(): Promise<React.ReactElement> {
  let entries: JournalEntry[] = [];
  let initialLoadError: string | undefined;

  try {
    entries = await listJournalEntries();
  } catch {
    initialLoadError = "Unable to load the journal.";
  }

  return <JournalView initialEntries={entries} initialLoadError={initialLoadError} />;
}
