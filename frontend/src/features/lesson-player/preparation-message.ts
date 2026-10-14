import type { PreparedSlot } from '@/lib/lesson-delivery-api';

type Preparation = PreparedSlot['preparation'];

// Keep diagnostic details in the job record; give the child one simple action.
export function needsMemoryHelp(preparation: Preparation): boolean {
  return preparation?.status === 'paused' || (
    preparation?.status === 'failed' && /memory|swap|critical|reclaimable|weights.*runtime/i.test(preparation.message)
  );
}

export function preparationMessage(preparation: Preparation): string {
  return needsMemoryHelp(preparation) ? 'close tabs and apps' : preparation?.message ?? '';
}
