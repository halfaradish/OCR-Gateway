import { useEffect } from "react";
import { useBlocker } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

/** Guards both `beforeunload` and in-app navigation while a form has unsaved changes. */
export function useUnsavedChanges(when: boolean) {
  const blocker = useBlocker(when);

  useEffect(() => {
    if (!when) return;
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [when]);

  return blocker;
}

export function LeaveConfirmDialog({
  blocker,
}: {
  blocker: ReturnType<typeof useUnsavedChanges>;
}) {
  return (
    <Dialog open={blocker.state === "blocked"} onOpenChange={(open) => !open && blocker.reset?.()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>放弃未保存的修改？</DialogTitle>
          <DialogDescription>离开此页后，本次填写的内容不会保留。</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button onClick={() => blocker.reset?.()}>继续编辑</Button>
          <Button variant="danger" onClick={() => blocker.proceed?.()}>
            放弃并离开
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
