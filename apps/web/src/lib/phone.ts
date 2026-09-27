/**
 * Mirrors apps/api/app/domain/phone.py exactly — the same pairing
 * whatsapp.ts has with app/domain/whatsapp.py, and for the same reason: the
 * two sides have to agree on what "the same number" means.
 *
 * The server is still the authority; it normalizes everything it stores
 * (decision 44). This copy exists so a form can tell someone their number
 * is short *while they are still looking at the field*, instead of a round
 * trip that lands on "something went wrong" three steps later.
 */
export function normalizePhone(value: string): string | null {
  const digits = value.replace(/[^\d]/g, '')
  if (!digits) return null

  let national: string
  if (digits.startsWith('00961')) national = digits.slice(5)
  else if (digits.startsWith('961')) national = digits.slice(3)
  // A local trunk prefix: 03 123456 is the same number as +961 3 123456.
  else if (digits.startsWith('0')) national = digits.slice(1)
  else national = digits

  // Lebanese mobiles are 7 digits (03 X XX XX XX) or 8 (70/71/76/78/79/81).
  if (national.length !== 7 && national.length !== 8) return null
  return `+961${national}`
}
