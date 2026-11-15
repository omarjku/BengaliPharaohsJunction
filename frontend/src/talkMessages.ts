export const SESSION_WARNING_MESSAGE = 'Talk ends in about 30 seconds. Finish your sentence; your order cards will stay on screen.'
export const SESSION_END_MESSAGE = 'Talk ended after 5 minutes - tap Talk to continue; your order cards are kept'

export function isSessionLimitMessage(message: string): boolean {
  return message === SESSION_END_MESSAGE || message === 'The conversation reached its 5-minute limit.'
}
