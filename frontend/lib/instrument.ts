export function formatInstrumentDisplay(
  instrument: string | null | undefined,
): string {
  if (typeof instrument !== 'string' || instrument.length === 0) return '';
  return instrument.replaceAll('_', '').replaceAll('/', '');
}
