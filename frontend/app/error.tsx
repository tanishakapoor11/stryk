"use client";

import { ErrorState } from "@/components/ui/states";
import { Button } from "@/components/ui/button";

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="mx-auto max-w-2xl px-4 py-16">
      <ErrorState
        title="Something went wrong rendering this analysis"
        detail={error.message}
      />
      <div className="mt-4 flex justify-center">
        <Button onClick={reset}>Try again</Button>
      </div>
    </div>
  );
}
