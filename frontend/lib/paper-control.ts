const RISK_PERCENTAGE_PATTERN = /^(?:\d+(?:\.\d*)?|\.\d+)$/;

const INVALID_RISK_PERCENTAGE =
  'Risk per trade must be a decimal percentage greater than 0% and less than 100%.';

export const PAPER_ACTIVATION_CONFIRMATION = 'ACTIVATE_PAPER' as const;
export const PAPER_STOP_REASON = 'Trader requested stop from Atlas UI.';

/** Convert a trader-entered percentage to an exact decimal ratio without floats. */
export function percentageToDecimalRatio(value: string): string {
  if (typeof value !== 'string') throw new TypeError(INVALID_RISK_PERCENTAGE);

  const input = value.trim();
  if (!RISK_PERCENTAGE_PATTERN.test(input)) {
    throw new RangeError(INVALID_RISK_PERCENTAGE);
  }

  const [wholeText, fractionalText = ''] = input.split('.');
  const whole = wholeText.replace(/^0+(?=\d)/, '') || '0';
  const fractional = fractionalText;
  const nonZeroFractional = /[1-9]/.test(fractional);

  if (
    whole === '100' ||
    whole.length > 3 ||
    (whole.length === 3 && whole > '100') ||
    (whole === '0' && !nonZeroFractional)
  ) {
    throw new RangeError(INVALID_RISK_PERCENTAGE);
  }

  const digits = `${whole}${fractional}`;
  const decimalIndex = whole.length - 2;
  let ratio: string;
  if (decimalIndex <= 0) {
    ratio = `0.${'0'.repeat(-decimalIndex)}${digits}`;
  } else if (decimalIndex >= digits.length) {
    ratio = `${digits}${'0'.repeat(decimalIndex - digits.length)}`;
  } else {
    ratio = `${digits.slice(0, decimalIndex)}.${digits.slice(decimalIndex)}`;
  }

  const [ratioWhole, ratioFraction = ''] = ratio.split('.');
  const normalizedWhole = ratioWhole.replace(/^0+(?=\d)/, '') || '0';
  const normalizedFraction = ratioFraction.replace(/0+$/, '');
  return normalizedFraction
    ? `${normalizedWhole}.${normalizedFraction}`
    : normalizedWhole;
}

const PAPER_LIFECYCLE_LABELS = {
  REQUESTED: 'Approved — waiting for Atlas runtime',
  STARTING: 'Starting',
  RUNNING: 'Running',
  STOP_REQUESTED: 'Stopping',
  STOPPED: 'Stopped',
  BLOCKED: 'Blocked',
  FAILED: 'Failed',
} as const;

const PAPER_OPERATIONAL_PHASE_LABELS = {
  IDLE: 'Waiting',
  STARTING: 'Starting',
  WAITING_FRONTIER: 'Waiting for next market frontier',
  WAITING_DATA: 'Waiting for market data',
  WAITING_PROVIDER: 'Waiting for broker',
  EVALUATING: 'Evaluating Strategy',
  EXECUTING: 'Executing approved Trade',
  RECOVERING: 'Recovering broker evidence',
  STOPPING: 'Stopping',
  BLOCKED: 'Blocked',
  FAILED: 'Failed',
} as const;

export function formatPaperLifecycle(value: string): string {
  return (
    PAPER_LIFECYCLE_LABELS[value as keyof typeof PAPER_LIFECYCLE_LABELS] ??
    value
  );
}

export function formatPaperOperationalPhase(value: string): string {
  return (
    PAPER_OPERATIONAL_PHASE_LABELS[
      value as keyof typeof PAPER_OPERATIONAL_PHASE_LABELS
    ] ?? value
  );
}
