import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * `inset` adds the panel gutter to the first/last cells; tables that sit directly on the
 * paper stay flush with the section heading above them.
 */
export function Table({
  className,
  inset = false,
  ...props
}: React.TableHTMLAttributes<HTMLTableElement> & { inset?: boolean }) {
  return (
    <div className="w-full overflow-x-auto">
      <table
        className={cn(
          "w-full text-body",
          inset &&
            "[&_th:first-child]:pl-5 [&_td:first-child]:pl-5 [&_th:last-child]:pr-5 [&_td:last-child]:pr-5",
          className,
        )}
        {...props}
      />
    </div>
  );
}

export function TableHead({ className, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <thead className={cn("text-left", className)} {...props} />;
}

export function TableBody({ className, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={cn("divide-y divide-line", className)} {...props} />;
}

export function TableRow({ className, ...props }: React.HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn("h-11 transition-colors hover:bg-mist/40", className)}
      {...props}
    />
  );
}

export function TableHeaderCell({
  className,
  ...props
}: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      scope="col"
      className={cn(
        "whitespace-nowrap border-b border-line pb-2 pr-4 pt-3 text-micro font-normal text-muted last:pr-0",
        className,
      )}
      {...props}
    />
  );
}

export function TableCell({ className, ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn("py-2 pr-4 align-middle last:pr-0", className)} {...props} />;
}
