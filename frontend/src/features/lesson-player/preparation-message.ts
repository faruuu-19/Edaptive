import type { PreparedSlot } from '@/lib/lesson-delivery-api';

type Preparation = PreparedSlot['preparation'];

export function preparationPercent(preparation: Preparation): number {
  return preparation?.status === 'ready' ? 100 : Math.max(0, Math.min(98, Math.round(preparation?.percent ?? 0)));
}

// Keep diagnostic details in the job record; give the child one simple action.
export function needsMemoryHelp(preparation: Preparation): boolean {
  return (preparation?.status === 'paused' && (!preparation.failure_kind || preparation.failure_kind === 'memory')) || (
    preparation?.status === 'failed' && (!preparation.failure_kind || preparation.failure_kind === 'memory') && /memory|swap|critical|reclaimable|weights.*runtime/i.test(preparation.message)
  );
}

export function preparationMessage(preparation: Preparation): string {
  return needsMemoryHelp(preparation) ? 'close tabs and apps' : preparation?.message ?? '';
}
