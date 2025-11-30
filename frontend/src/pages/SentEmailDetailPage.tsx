import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card'
import { toast } from 'sonner'
import { ArrowLeft, Mail, Calendar, Paperclip, Users, Eye, EyeOff, Shield, AlertTriangle, Info, FileText } from 'lucide-react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// PII 타입 한글명 변환
const getPIITypeKorean = (type: string): string => {
  const typeMap: Record<string, string> = {
    'email': '이메일 주소',
    'phone': '전화번호',
    'jumin': '주민등록번호',
    'account': '계좌번호',
    'passport': '여권번호',
    'driver_license': '운전면허번호',
    'name': '이름',
    'address': '주소',
    'company': '회사명',
  }
  return typeMap[type] || type
}

// Risk level에 따른 색상 반환 (톤 다운된 색상 사용)
const getRiskBadgeColor = (riskLevel: string) => {
  switch (riskLevel) {
    case 'high':
      return 'bg-red-50 text-red-700 border-red-200' // Destructive 느낌 유지하되 부드럽게
    case 'medium':
      return 'bg-amber-50 text-amber-700 border-amber-200' // Warning
    case 'low':
      return 'bg-primary/10 text-primary border-primary/20' // Safe
    default:
      return 'bg-slate-100 text-slate-700 border-slate-200'
  }
}

// Risk level에 따른 아이콘 반환
const getRiskIcon = (riskLevel: string) => {
  switch (riskLevel) {
    case 'high':
      return <AlertTriangle className="h-3 w-3" />
    case 'medium':
      return <Shield className="h-3 w-3" />
    case 'low':
      return <Info className="h-3 w-3" />
    default:
      return null
  }
}

interface SentEmailDetailPageProps {
  emailId: string
  onBack?: () => void
}

interface EmailData {
  _id: string
  from_email: string
  to_emails?: string[]
  to_email?: string
  subject: string
  body?: string
  original_body?: string
  attachments?: AttachmentInfo[]
  created_at: string
  sent_at?: string
  status?: string
  masking_decisions?: any
  pii_masked_count?: number
}

interface AttachmentInfo {
  filename: string
  content_type: string
  size: number
  data?: string
}

interface MaskedEmailData {
  email_id: string
  from_email: string
  to_emails: string[]
  subject: string
  masked_body: string
  masked_attachments: AttachmentInfo[]
  masking_decisions: Record<string, PIIDecision>
  pii_masked_count: number
  created_at: string
}

interface PIIDecision {
  pii_id: string
  type: string
  value: string
  should_mask: boolean
  masking_method: string
  masked_value?: string
  reason: string
  reasoning: string
  cited_guidelines: string[]
  guideline_matched: boolean
  confidence: number
  risk_level: 'low' | 'medium' | 'high'
}

// 마스킹된 텍스트를 hover card와 함께 렌더링하는 컴포넌트
function MaskedTextWithMetadata({ text, decisions, originalText }: {
  text: string
  decisions: Record<string, PIIDecision>
  originalText?: string
}) {
  if (!text || !decisions || Object.keys(decisions).length === 0) {
    return <span>{text}</span>
  }

  // decisions 객체를 배열로 변환하면서 pii_id를 추가
  const decisionsArray = Object.entries(decisions)
    .map(([key, value]) => ({ ...value, pii_id: key }))
    .filter(d => d.should_mask && d.masked_value)

  if (decisionsArray.length === 0) {
    return <span>{text}</span>
  }

  interface MaskMatch {
    start: number
    end: number
    decision: PIIDecision
  }

  const matches: MaskMatch[] = []

  if (originalText && originalText.length > 0) {
    interface MaskPattern {
      value: string
      start: number
      end: number
    }

    const maskPatterns: MaskPattern[] = []
    let i = 0
    while (i < text.length) {
      if (text[i] === '*') {
        const start = i
        while (i < text.length && text[i] === '*') {
          i++
        }
        maskPatterns.push({
          value: text.substring(start, i),
          start,
          end: i
        })
      } else {
        i++
      }
    }

    const sortedDecisions = [...decisionsArray].sort((a, b) => {
      const getIdNumber = (pii_id: string | undefined): number => {
        if (!pii_id) return 9999
        const match = pii_id.match(/\d+/)
        return match ? parseInt(match[0]) : 9999
      }
      return getIdNumber(a.pii_id) - getIdNumber(b.pii_id)
    })

    let patternIndex = 0
    for (const decision of sortedDecisions) {
      const maskedValue = decision.masked_value || '***'
      let found = false
      for (let j = patternIndex; j < maskPatterns.length; j++) {
        const pattern = maskPatterns[j]
        if (pattern.value === maskedValue) {
          matches.push({
            start: pattern.start,
            end: pattern.end,
            decision
          })
          patternIndex = j + 1
          found = true
          break
        }
      }
    }
  } else {
    let searchIndex = 0
    for (const decision of decisionsArray) {
      const maskedValue = decision.masked_value || '***'
      const position = text.indexOf(maskedValue, searchIndex)

      if (position !== -1) {
        matches.push({
          start: position,
          end: position + maskedValue.length,
          decision
        })
        searchIndex = position + maskedValue.length
      }
    }
  }

  const filteredMatches = matches
  const parts: React.ReactNode[] = []
  let lastIndex = 0

  filteredMatches.forEach((match, idx) => {
    if (match.start > lastIndex) {
      parts.push(
        <span key={`text-${idx}`}>
          {text.substring(lastIndex, match.start)}
        </span>
      )
    }

    // 마스킹 하이라이트 스타일 변경 (Secondary color 활용)
    parts.push(
      <HoverCard key={`masked-${idx}`} openDelay={200} closeDelay={100}>
        <HoverCardTrigger asChild>
          <span className="cursor-help text-primary px-0.5 rounded border-b border-primary/30 transition-colors font-medium" style={{ backgroundColor: 'hsl(168.4 83.8% 78.2% / 0.2)' } as React.CSSProperties} onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'hsl(168.4 83.8% 78.2% / 0.3)'}>
            {text.substring(match.start, match.end)}
          </span>
        </HoverCardTrigger>
        <HoverCardContent className="w-80 z-50 border-primary/20" side="top" align="start" sideOffset={5}>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-semibold flex items-center gap-1 text-slate-800">
                {getRiskIcon(match.decision.risk_level)}
                PII 상세 정보
              </h4>
              <Badge className={`text-xs ${getRiskBadgeColor(match.decision.risk_level)} shadow-none`}>
                {match.decision.risk_level.toUpperCase()}
              </Badge>
            </div>

            <div className="space-y-1 text-xs text-slate-600">
              <div className="flex justify-between gap-2">
                <span className="text-slate-500 shrink-0">PII 유형:</span>
                <span className="font-medium text-right">{getPIITypeKorean(match.decision.type)}</span>
              </div>
              <div className="flex justify-between gap-2">
                <span className="text-slate-500 shrink-0">원본 값:</span>
                {/* 원본값은 민감하므로 붉은 계열 유지하되 톤다운 */}
                <span className="font-mono text-red-600/80 text-right break-all">{match.decision.value}</span>
              </div>
              <div className="flex justify-between gap-2">
                <span className="text-slate-500 shrink-0">마스킹 값:</span>
                <span className="font-mono text-primary text-right break-all font-semibold">{match.decision.masked_value}</span>
              </div>
              <div className="flex justify-between gap-2">
                <span className="text-slate-500 shrink-0">마스킹 방법:</span>
                <Badge variant="outline" className="text-[10px] h-5 px-1 bg-slate-50">
                  {match.decision.masking_method === 'full' ? '전체' : '부분'}
                </Badge>
              </div>
            </div>

            <div className="pt-2 border-t border-slate-100">
              <p className="text-xs font-medium mb-1 text-slate-700">마스킹 이유:</p>
              <p className="text-xs text-slate-500 leading-relaxed">{match.decision.reason}</p>
            </div>

            {match.decision.cited_guidelines && match.decision.cited_guidelines.length > 0 && (
              <div className="pt-2 border-t border-slate-100">
                <p className="text-xs font-medium mb-1 text-slate-700">적용된 규정:</p>
                <ul className="text-xs text-slate-500 space-y-1">
                  {match.decision.cited_guidelines.slice(0, 3).map((guideline, i) => (
                    <li key={i} className="flex items-start gap-1">
                      <span className="text-primary shrink-0">•</span>
                      <span className="leading-relaxed">{guideline}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
              <span className="text-slate-500">AI 신뢰도:</span>
              <span className="font-medium text-primary">{(match.decision.confidence * 100).toFixed(0)}%</span>
            </div>
          </div>
        </HoverCardContent>
      </HoverCard>
    )

    lastIndex = match.end
  })

  if (lastIndex < text.length) {
    parts.push(
      <span key="text-end">{text.substring(lastIndex)}</span>
    )
  }

  return <>{parts}</>
}

export const SentEmailDetailPage: React.FC<SentEmailDetailPageProps> = ({
  emailId,
  onBack,
}) => {
  const [originalEmail, setOriginalEmail] = useState<EmailData | null>(null)
  const [maskedEmail, setMaskedEmail] = useState<MaskedEmailData | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeView, setActiveView] = useState<'compare' | 'original' | 'masked'>('compare')
  const [originalAttachmentUrls, setOriginalAttachmentUrls] = useState<Map<string, string>>(new Map())
  const [maskedAttachmentUrls, setMaskedAttachmentUrls] = useState<Map<string, string>>(new Map())

  useEffect(() => {
    loadEmailDetails()
    return () => {
      originalAttachmentUrls.forEach(url => URL.revokeObjectURL(url))
      maskedAttachmentUrls.forEach(url => URL.revokeObjectURL(url))
    }
  }, [emailId])

  const loadEmailDetails = async () => {
    setLoading(true)
    let hasMaskedData = false
    try {
      const token = localStorage.getItem('auth_token')

      const emailResponse = await fetch(`${API_BASE_URL}/api/v1/files/original_emails/${emailId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })

      if (!emailResponse.ok) throw new Error('원본 이메일을 불러오는데 실패했습니다.')

      const emailResult = await emailResponse.json()
      if (emailResult.success && emailResult.data) {
        setOriginalEmail(emailResult.data)
        if (emailResult.data.attachments) {
          const urlMap = new Map<string, string>()
          for (const attachment of emailResult.data.attachments) {
            try {
              const binaryString = atob(attachment.data)
              const bytes = new Uint8Array(binaryString.length)
              for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i)
              }
              const blob = new Blob([bytes], { type: attachment.content_type })
              const url = URL.createObjectURL(blob)
              urlMap.set(attachment.filename, url)
            } catch (error) {
              console.error(`원본 첨부파일 로드 실패: ${attachment.filename}`, error)
            }
          }
          setOriginalAttachmentUrls(urlMap)
        }
      }

      const maskedResponse = await fetch(`${API_BASE_URL}/api/v1/files/masked_emails/${emailId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })

      if (maskedResponse.ok) {
        const maskedResult = await maskedResponse.json()
        if (maskedResult.success && maskedResult.data) {
          setMaskedEmail(maskedResult.data)
          hasMaskedData = true

          if (maskedResult.data.masked_attachments) {
            const urlMap = new Map<string, string>()
            for (const attachment of maskedResult.data.masked_attachments) {
              try {
                const binaryString = atob(attachment.data)
                const bytes = new Uint8Array(binaryString.length)
                for (let i = 0; i < binaryString.length; i++) {
                  bytes[i] = binaryString.charCodeAt(i)
                }
                const blob = new Blob([bytes], { type: attachment.content_type })
                const url = URL.createObjectURL(blob)
                urlMap.set(attachment.filename, url)
              } catch (error) {
                console.error(`마스킹 첨부파일 로드 실패: ${attachment.filename}`, error)
              }
            }
            setMaskedAttachmentUrls(urlMap)
          }
        }
      }

    } catch (error: any) {
      console.error('이메일 조회 오류:', error)
      toast.error(error.message || '이메일을 불러오는데 실패했습니다.')
    } finally {
      setLoading(false)
      if (!hasMaskedData) {
        setActiveView('original')
      }
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const htmlToText = (html: string): string => {
    if (!html) return ''
    const tempDiv = document.createElement('div')
    tempDiv.innerHTML = html
    tempDiv.innerHTML = tempDiv.innerHTML
      .replace(/<br\s*\/?>/gi, '\n')
      .replace(/<\/div>/gi, '\n')
      .replace(/<\/p>/gi, '\n\n')
      .replace(/<div>/gi, '')
      .replace(/<p>/gi, '')
    return tempDiv.textContent || tempDiv.innerText || ''
  }

  const renderAttachment = (attachment: AttachmentInfo, urlMap: Map<string, string>, isMasked: boolean = false) => {
    const url = urlMap.get(attachment.filename)

    if (!url) {
      return <div className="text-sm text-slate-500">로딩 중...</div>
    }

    const isImage = attachment.content_type.startsWith('image/')
    const isPDF = attachment.content_type === 'application/pdf'
    
    // 첨부파일 박스 스타일
    const boxStyle = isMasked 
      ? "p-4 border border-primary/20 rounded bg-secondary/30" 
      : "p-4 border border-slate-200 rounded bg-slate-50"

    const linkStyle = isMasked 
      ? "text-primary text-sm font-medium hover:underline underline-offset-4" 
      : "text-slate-600 text-sm font-medium hover:underline underline-offset-4"

    if (isImage) {
      return (
        <img
          src={url}
          alt={`${attachment.filename} 미리보기`}
          className="max-w-full h-auto border rounded border-slate-200"
        />
      )
    } else if (isPDF) {
      return (
        <div className="space-y-2">
          <object
            data={url}
            type="application/pdf"
            className="w-full h-[500px] border rounded border-slate-200"
          >
            <p className="text-sm text-slate-500">
              PDF를 미리볼 수 없습니다.
            </p>
          </object>
          <div className="text-right">
             <a href={url} download={attachment.filename} className={linkStyle}>
              PDF 다운로드
            </a>
          </div>
        </div>
      )
    }

    return (
      <div className={boxStyle}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Paperclip className={`h-4 w-4 ${isMasked ? 'text-primary' : 'text-slate-400'}`} />
            <span className={`text-sm ${isMasked ? 'text-slate-800' : 'text-slate-600'}`}>
              {attachment.filename}
            </span>
          </div>
          <a href={url} download={attachment.filename} className={linkStyle}>
            다운로드
          </a>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="container mx-auto max-w-7xl p-6">
        <div className="text-center py-20">
          <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-slate-500">데이터를 불러오는 중입니다...</p>
        </div>
      </div>
    )
  }

  if (!originalEmail) {
    return (
      <div className="container mx-auto max-w-7xl p-6">
        <Card className="border-red-100 bg-red-50/50">
          <CardContent className="pt-6">
            <p className="text-red-600 text-center flex items-center justify-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              이메일 데이터를 찾을 수 없습니다.
            </p>
            {onBack && (
              <Button variant="ghost" onClick={onBack} className="mt-4 mx-auto block hover:bg-red-100 text-red-600">
                <ArrowLeft className="mr-2 h-4 w-4" />
                목록으로 돌아가기
              </Button>
            )}
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="container mx-auto max-w-7xl p-6 space-y-6">
      {/* 헤더 섹션 */}
      <div className="flex items-center justify-between pb-4 border-b border-slate-100">
        {onBack && (
          <Button variant="outline" onClick={onBack} className="border-slate-200 text-slate-700 hover:bg-slate-50">
            <ArrowLeft className="mr-2 h-4 w-4" />
            뒤로 가기
          </Button>
        )}
      </div>

      {/* 이메일 메타 정보 카드 (색상 통일: 화이트 베이스 + Primary 강조) */}
      <Card className="border-slate-200 shadow-sm bg-white">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <CardTitle className="text-xl font-semibold text-slate-900">{originalEmail.subject}</CardTitle>
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Calendar className="h-3.5 w-3.5" />
                {formatDate(originalEmail.created_at)}
              </div>
            </div>
            {maskedEmail && (
              <Badge className="bg-primary hover:bg-primary/90 text-primary-foreground border-transparent px-3 py-1 text-sm font-normal">
                분석 완료
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-y-4 gap-x-8 text-sm pt-2 border-t border-slate-100">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-8 h-8 rounded-full bg-slate-100 text-slate-500">
                <Mail className="h-4 w-4" />
              </div>
              <div>
                <span className="block text-xs text-slate-500">발신자</span>
                <span className="font-medium text-slate-900">{originalEmail.from_email}</span>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-8 h-8 rounded-full bg-slate-100 text-slate-500">
                <Users className="h-4 w-4" />
              </div>
              <div>
                <span className="block text-xs text-slate-500">수신자</span>
                <span className="font-medium text-slate-900">
                  {originalEmail.to_emails?.join(', ') || originalEmail.to_email}
                </span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 통계 요약 (Primary Color 중심) */}
      {maskedEmail && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="border-primary/20 bg-secondary/30 shadow-sm">
            <CardContent className="p-4 flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-primary uppercase">Masked PII</p>
                <p className="text-2xl font-bold text-slate-900 mt-1">{maskedEmail.pii_masked_count || 0}<span className="text-sm font-normal text-slate-500 ml-1">건</span></p>
              </div>
              <div className="h-10 w-10 rounded-full bg-white flex items-center justify-center text-primary shadow-sm border border-primary/10">
                <Shield className="h-5 w-5" />
              </div>
            </CardContent>
          </Card>
          <Card className="border-slate-200 bg-white shadow-sm">
            <CardContent className="p-4 flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-slate-500 uppercase">Attachments</p>
                <p className="text-2xl font-bold text-slate-900 mt-1">{maskedEmail.masked_attachments?.length || 0}<span className="text-sm font-normal text-slate-500 ml-1">개</span></p>
              </div>
              <div className="h-10 w-10 rounded-full bg-slate-50 flex items-center justify-center text-slate-400 border border-slate-100">
                <Paperclip className="h-5 w-5" />
              </div>
            </CardContent>
          </Card>
          <Card className="border-slate-200 bg-white shadow-sm">
            <CardContent className="p-4 flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-slate-500 uppercase">Applied Rules</p>
                <p className="text-2xl font-bold text-slate-900 mt-1">{Object.keys(maskedEmail.masking_decisions || {}).length}<span className="text-sm font-normal text-slate-500 ml-1">개</span></p>
              </div>
              <div className="h-10 w-10 rounded-full bg-slate-50 flex items-center justify-center text-slate-400 border border-slate-100">
                <FileText className="h-5 w-5" />
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* 뷰 컨트롤러 */}
      {maskedEmail && (
        <div className="flex justify-center py-2">
          <div className="inline-flex bg-slate-100 p-1 rounded-lg border border-slate-200">
            {(['compare', 'original', 'masked'] as const).map((view) => (
              <button
                key={view}
                onClick={() => setActiveView(view)}
                className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all duration-200 ${
                  activeView === view
                    ? 'bg-white text-slate-900 shadow-sm'
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                {view === 'compare' && '비교 보기'}
                {view === 'original' && '원본만 보기'}
                {view === 'masked' && '결과만 보기'}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 비교 보기 */}
      {activeView === 'compare' && maskedEmail && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 원본 */}
          <Card className="border-slate-200 shadow-lg">
            <CardHeader className="bg-slate-50 border-b border-slate-200">
              <CardTitle className="text-base flex items-center gap-2">
                <EyeOff className="h-5 w-5 text-slate-500" />
                원본 (마스킹 전)
              </CardTitle>
              <CardDescription className="text-xs text-slate-500">
                실제 전송되지 않은 원본 데이터입니다
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-4 space-y-4">
              {/* 본문 */}
              <div>
                <div className="bg-slate-50 border border-slate-200 rounded p-4 text-sm whitespace-pre-wrap max-h-[400px] overflow-y-auto text-slate-800">
                  {htmlToText(originalEmail.original_body || originalEmail.body || '')}
                </div>
              </div>

              {/* 첨부파일 */}
              {originalEmail.attachments && originalEmail.attachments.length > 0 && (
                <div>
                  <h4 className="font-semibold text-sm mb-2 text-slate-700">
                    📎 첨부파일 ({originalEmail.attachments.length}개)
                  </h4>
                  <div className="space-y-3">
                    {originalEmail.attachments.map((att, idx) => (
                      <div key={idx} className="border border-slate-200 rounded p-3 bg-white">
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-medium text-sm text-slate-700">{att.filename}</span>
                          <Badge variant="outline" className="text-xs text-slate-500">{att.content_type}</Badge>
                        </div>
                        {renderAttachment(att, originalAttachmentUrls)}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* 마스킹 */}
          <Card className="border-primary/50 shadow-lg bg-secondary/10">
            <CardHeader style={{ backgroundColor: 'hsl(168.4 83.8% 78.2% / 0.2)' } as React.CSSProperties} className="border-b border-primary/50">
              <CardTitle className="text-base flex items-center gap-2">
                <Eye className="h-5 w-5 text-primary" />
                마스킹 결과 (전송됨)
              </CardTitle>
              <CardDescription className="text-xs text-slate-600">
                실제 수신자에게 전송된 마스킹 처리된 데이터입니다
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-4 space-y-4">
              {/* 본문 */}
              <div>
                <div className="bg-white border border-primary/20 rounded p-4 text-sm whitespace-pre-wrap max-h-[400px] overflow-y-auto text-slate-800">
                  <MaskedTextWithMetadata
                    text={htmlToText(maskedEmail.masked_body || '본문이 없습니다')}
                    decisions={maskedEmail.masking_decisions || {}}
                    originalText={htmlToText(originalEmail.original_body || originalEmail.body || '')}
                  />
                </div>
              </div>

              {/* 첨부파일 */}
              {maskedEmail.masked_attachments && maskedEmail.masked_attachments.length > 0 && (
                <div>
                  <h4 className="font-semibold text-sm mb-2 text-slate-900">
                    📎 첨부파일 ({maskedEmail.masked_attachments.length}개)
                  </h4>
                  <div className="space-y-3">
                    {maskedEmail.masked_attachments.map((att, idx) => (
                      <div key={idx} className="border border-primary/20 rounded p-3 bg-white">
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-medium text-sm text-slate-900">{att.filename}</span>
                          <Badge variant="outline" className="text-xs bg-secondary text-primary border-primary/20">{att.content_type}</Badge>
                        </div>
                        {renderAttachment(att, maskedAttachmentUrls)}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* 원본만 보기 */}
      {activeView === 'original' && (
        <Card className="border-slate-200">
          <CardHeader className="bg-slate-50 border-b border-slate-100">
            <CardTitle className="text-sm flex items-center gap-2 text-slate-700">
              <EyeOff className="h-4 w-4" />
              원본 이메일
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-4 space-y-4">
            {/* 본문 */}
            <div>
              <div className="bg-slate-50 border border-slate-200 rounded p-4 text-sm whitespace-pre-wrap max-h-[600px] overflow-y-auto text-slate-800">
                {htmlToText(originalEmail.original_body || originalEmail.body || '본문이 없습니다')}
              </div>
            </div>

            {/* 첨부파일 */}
            {originalEmail.attachments && originalEmail.attachments.length > 0 && (
              <div>
                <h4 className="font-semibold mb-2 text-slate-700">
                  📎 첨부파일 ({originalEmail.attachments.length}개)
                </h4>
                <div className="space-y-4">
                  {originalEmail.attachments.map((att, idx) => (
                    <div key={idx} className="border border-slate-200 rounded p-4 bg-white">
                      <div className="flex items-center justify-between mb-3">
                        <span className="font-medium text-slate-700">{att.filename}</span>
                        <Badge variant="outline" className="text-slate-500">{att.content_type}</Badge>
                      </div>
                      {renderAttachment(att, originalAttachmentUrls)}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* 마스킹만 보기 */}
      {activeView === 'masked' && maskedEmail && (
        <Card className="border-primary/50 shadow-lg bg-secondary/10">
            <CardHeader style={{ backgroundColor: 'hsl(168.4 83.8% 78.2% / 0.2)' } as React.CSSProperties} className="border-b border-primary/50">
            <CardTitle className="text-sm flex items-center gap-2 text-primary-dark">
              <Eye className="h-4 w-4 text-primary" />
              마스킹된 이메일
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-4 space-y-4">
            {/* 본문 */}
            <div>

              <div className="bg-white border border-primary/20 rounded p-4 text-sm whitespace-pre-wrap max-h-[600px] overflow-y-auto text-slate-800">
                <MaskedTextWithMetadata
                  text={htmlToText(maskedEmail.masked_body || '본문이 없습니다')}
                  decisions={maskedEmail.masking_decisions || {}}
                  originalText={htmlToText(originalEmail.original_body || originalEmail.body || '')}
                />
              </div>
            </div>

            {/* 첨부파일 */}
            {maskedEmail.masked_attachments && maskedEmail.masked_attachments.length > 0 && (
              <div>
                <h4 className="font-semibold mb-2 text-slate-900">
                  📎 첨부파일 ({maskedEmail.masked_attachments.length}개)
                </h4>
                <div className="space-y-4">
                  {maskedEmail.masked_attachments.map((att, idx) => (
                    <div key={idx} className="border border-primary/20 rounded p-4 bg-white">
                      <div className="flex items-center justify-between mb-3">
                        <span className="font-medium text-slate-900">{att.filename}</span>
                        <Badge variant="outline" className="bg-secondary text-primary border-primary/20">{att.content_type}</Badge>
                      </div>
                      {renderAttachment(att, maskedAttachmentUrls)}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}