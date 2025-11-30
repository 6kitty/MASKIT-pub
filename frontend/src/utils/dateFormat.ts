/**
 * 날짜를 한국 시간(KST)으로 포맷팅
 */
export const formatDate = (dateString: string | Date): string => {
  const date = typeof dateString === 'string' ? new Date(dateString) : dateString

  return date.toLocaleString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Seoul'
  })
}

/**
 * 날짜만 포맷팅 (시간 제외)
 */
export const formatDateOnly = (dateString: string | Date): string => {
  const date = typeof dateString === 'string' ? new Date(dateString) : dateString

  return date.toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    timeZone: 'Asia/Seoul'
  })
}

/**
 * 시간만 포맷팅 (날짜 제외)
 */
export const formatTimeOnly = (dateString: string | Date): string => {
  const date = typeof dateString === 'string' ? new Date(dateString) : dateString

  return date.toLocaleTimeString('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Seoul'
  })
}

/**
 * 상대 시간 표시 (예: "5분 전", "3일 전")
 */
export const formatRelativeTime = (dateString: string | Date): string => {
  const date = typeof dateString === 'string' ? new Date(dateString) : dateString
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHour = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHour / 24)

  if (diffSec < 60) return '방금 전'
  if (diffMin < 60) return `${diffMin}분 전`
  if (diffHour < 24) return `${diffHour}시간 전`
  if (diffDay < 7) return `${diffDay}일 전`

  return formatDate(date)
}
