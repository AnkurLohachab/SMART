import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Returns '-' instead of "Invalid Date". Handles ISO strings, epoch numbers,
// Date objects, and the Neo4j driver's DateTime JSON shape.
export function safeDate(input: any, mode: 'date' | 'datetime' = 'date'): string {
  if (input === null || input === undefined || input === '') return '-';

  if (typeof input === 'object' && input?._DateTime__date) {
    const dt = input._DateTime__date;
    const y = dt._Date__year;
    const m = String(dt._Date__month ?? 1).padStart(2, '0');
    const d = String(dt._Date__day ?? 1).padStart(2, '0');
    if (y) return `${y}-${m}-${d}`;
  }

  const d = input instanceof Date ? input : new Date(input);
  if (Number.isNaN(d.getTime())) return '-';
  return mode === 'datetime' ? d.toLocaleString() : d.toLocaleDateString();
}

// Maps internal status enums to user-facing labels. Storage/wire names stay unchanged.
const STATUS_DISPLAY_MAP: Record<string, string> = {
  Created: 'Draft',
  InEvaluation: 'Under Review',
  Validated: 'Reviewed',
  Rejected: 'Declined',
  RevisionRequested: 'Changes Requested',
  Revised: 'Revised',
  Published: 'Published',
  Deprecated: 'Archived',
};

export function displayStatus(status: string | null | undefined): string {
  if (!status) return '-';
  return STATUS_DISPLAY_MAP[status] || status;
}
