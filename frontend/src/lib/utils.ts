export function formatCartStatus(status: string): string {
  const statusMap: Record<string, string> = {
    ACTIVE: 'Active',
    VERIFIED: 'Verified',
    AWAITING_APPROVAL: 'Awaiting Approval',
    APPROVED_FOR_PAYMENT: 'Approved for Payment',
    PAID: 'Paid',
    CANCELLED: 'Cancelled',
  };
  return statusMap[status] || status.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
