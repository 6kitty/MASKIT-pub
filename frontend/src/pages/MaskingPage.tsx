import React, { useState, useEffect, useRef } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { toast } from 'sonner'
import { Send } from 'lucide-react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// 스크롤바 숨기기 스타일 + 애니메이션
const scrollbarHideStyle = `
  .scrollbar-hide::-webkit-scrollbar {
    display: none;
  }
  @keyframes fade-in {
    from {
      opacity: 0;
      transform: translateY(-4px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
  .animate-fade-in {
    animation: fade-in 0.3s ease-out;
  }
`

interface MaskingPageProps {
  emailData: EmailData
  onBack?: () => void
  onSendComplete?: () => void
}

interface EmailData {
  from: string
  to: string[]
  subject: string
  body: string
  attachments: (AttachmentInfo | File)[]
  email_id?: string // MongoDB에 저장된 원본 이메일 ID
}

interface AttachmentInfo {
  file_id: string
  filename: string
  size: number
  content_type: string
}

interface PIIItem {
  type: string
  value: string
}

interface MaskingDecision {
  type: string
  value: string
  should_mask: boolean
  reason: string
  masked_value?: string
  risk_level?: string
  reasoning?: string
  cited_guidelines?: string[]
}

interface AnalysisContext {
  sender_type: string | null
  receiver_type: string | null
  purpose: string[]
  regulations: string[]
}

interface PIICoordinate {
  pageIndex: number
  bbox: number[]
  field_text: string
}

interface DetectedPIIEntity {
  text: string
  type: string
  score: number
  start_char: number
  end_char: number
  coordinates?: PIICoordinate[]
}

interface PIIAnalysisResult {
  full_text: string
  pii_entities: DetectedPIIEntity[]
}

interface FileAnalysisResult {
  filename: string
  status: string
  analysis_data?: PIIAnalysisResult
  ocr_data?: any
}

export const MaskingPage: React.FC<MaskingPageProps> = ({
  emailData,
  onBack,
  onSendComplete,
}) => {
  const [attachmentUrls, setAttachmentUrls] = useState<Map<string, string>>(new Map())
  const [maskingDecisions, setMaskingDecisions] = useState<Record<string, MaskingDecision>>({})

  // 통합된 모든 PII 목록 (체크박스용)
  const [allPIIList, setAllPIIList] = useState<Array<{
    id: string
    type: string
    value: string
    source: 'regex' | 'backend_body' | 'backend_attachment'
    filename?: string
    shouldMask: boolean
    maskingDecision?: MaskingDecision
    coordinate?: PIICoordinate  // 첨부파일 PII의 좌표 정보
    entityIndex?: number  // 원본 entity 인덱스
    start_char?: number
  }>>([])
  const [showPIICheckboxList, setShowPIICheckboxList] = useState(false)
  const [aiSummary, setAiSummary] = useState('커스텀 설정을 선택하고 분석을 시작하세요.')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [analysisProgress, setAnalysisProgress] = useState<string>('') // PII 분석 진행률
  const [isSending, setIsSending] = useState(false)
  const [isMasking, setIsMasking] = useState(false)
  const [maskedBody, setMaskedBody] = useState<string>('')
  const [maskedAttachmentFilenames, setMaskedAttachmentFilenames] = useState<string[]>([])
  const [showMaskedPreview, setShowMaskedPreview] = useState(false)
  const [maskedAttachmentUrls, setMaskedAttachmentUrls] = useState<Map<string, string>>(new Map())

  // 원본 이메일 데이터 (MongoDB에서 불러온)
  const [originalEmailData, setOriginalEmailData] = useState<any>(null)
  const [isLoadingOriginal, setIsLoadingOriginal] = useState(false)

  // Context 선택 상태
  const [senderContext, setSenderContext] = useState<string>('')
  const [receiverContext, setReceiverContext] = useState<string>('')
  const [purposes, setPurposes] = useState<string[]>([])
  const [regulations, setRegulations] = useState<string[]>([])

  const emailBodyRef = useRef<HTMLDivElement>(null)

  // MongoDB에서 원본 이메일 불러오기
  useEffect(() => {
    if (emailData.email_id) {
      loadOriginalEmail(emailData.email_id)
    }
  }, [emailData.email_id])

  // 초기화 (originalEmailData가 없을 때만)
  useEffect(() => {
    loadEmailBody()
    // originalEmailData가 로드되면 그쪽에서 loadAttachments 호출되므로 중복 방지
    if (!emailData.email_id) {
      loadAttachments()
    }
    // detectPII()는 AI 분석 시 실행되므로 초기화 시 제거
  }, [emailData.email_id]) // email_id만 의존성으로 설정하여 불필요한 재호출 방지

  // 원본 이메일 데이터 로드 후에는 자동 분석하지 않음 (사용자가 커스텀 설정 후 분석 버튼 클릭)
  // useEffect 제거하여 자동 PII 분석 방지

  // 원본 데이터 로드 후 첨부파일 다시 로드
  useEffect(() => {
    if (originalEmailData && originalEmailData.attachments) {
      loadAttachments()
    }
  }, [originalEmailData?._id]) // _id로 변경하여 실제 데이터가 변경될 때만 호출

  // MongoDB에서 원본 이메일 데이터 불러오기
  const loadOriginalEmail = async (email_id: string) => {
    setIsLoadingOriginal(true)
    try {
      console.log('📧 원본 이메일 조회 시작:', email_id)
      const response = await fetch(`${API_BASE_URL}/api/v1/files/original_emails/${email_id}`)

      if (response.ok) {
        const result = await response.json()
        console.log('📦 API 응답 전체:', result)

        if (result.success && result.data) {
          console.log('✅ 원본 이메일 데이터:', {
            email_id: result.data.email_id,
            from_email: result.data.from_email,
            to_emails: result.data.to_emails,
            subject: result.data.subject,
            has_original_body: !!result.data.original_body,
            has_body: !!result.data.body,
            original_body_length: result.data.original_body?.length,
            body_length: result.data.body?.length,
            attachments_count: result.data.attachments?.length
          })
          setOriginalEmailData(result.data)
        }
      } else {
        console.error('❌ 원본 이메일 로드 실패:', response.status)
      }
    } catch (error) {
      console.error('❌ 원본 이메일 로드 중 오류:', error)
    } finally {
      setIsLoadingOriginal(false)
    }
  }

  // HTML을 텍스트로 변환 (줄바꿈 보존)
  const htmlToText = (html: string): string => {
    if (!html) return ''
    const tempDiv = document.createElement('div')
    tempDiv.innerHTML = html
    tempDiv.innerHTML = tempDiv.innerHTML
      .replace(/<br\s*\/?>/gi, '\n')
      .replace(/<\/div>/gi, '\n')
      .replace(/<\/p>/gi, '\n')
      .replace(/<div>/gi, '')
      .replace(/<p>/gi, '')
    return tempDiv.textContent || tempDiv.innerText || ''
  }

  // 이메일 본문 로드 (더 이상 필요 없음 - htmlToText 직접 사용)
  const loadEmailBody = () => {
    // 본문은 마스킹 시점에 htmlToText로 변환됨
  }

  // 첨부파일 Blob URL 생성 (MongoDB에서 Base64 디코딩)
  const loadAttachments = async () => {
    const urlMap = new Map<string, string>()

    // MongoDB에서 불러온 원본 데이터가 있으면 그것을 사용
    if (originalEmailData?.attachments) {
      for (const attachment of originalEmailData.attachments) {
        try {
          // Base64 데이터를 Blob으로 변환
          const binaryString = atob(attachment.data)
          const bytes = new Uint8Array(binaryString.length)
          for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i)
          }
          const blob = new Blob([bytes], { type: attachment.content_type })
          const url = URL.createObjectURL(blob)

          // filename을 키로 사용
          urlMap.set(attachment.filename, url)
          console.log(`✅ 첨부파일 로드 성공: ${attachment.filename}`)
        } catch (error) {
          console.error(`첨부파일 로드 실패: ${attachment.filename}`, error)
        }
      }
    } else {
      // 기존 방식 (file_id 사용)
      for (const attachment of emailData.attachments) {
        if ((attachment as any).file_id) {
          try {
            const token = localStorage.getItem('auth_token')
            const response = await fetch(`${API_BASE_URL}/api/v1/emails/attachments/${(attachment as any).file_id}`, {
              headers: { 'Authorization': `Bearer ${token}` }
            })

            if (response.ok) {
              const blob = await response.blob()
              const url = URL.createObjectURL(blob)
              urlMap.set((attachment as any).file_id, url)
            }
          } catch (error) {
            console.error(`첨부파일 로드 실패:`, error)
          }
        }
      }
    }

    setAttachmentUrls(urlMap)
  }

  // 컴포넌트 언마운트 시에만 Blob URL 해제 (의존성 배열 제거)
  useEffect(() => {
    return () => {
      // 컴포넌트가 언마운트될 때만 실행
      attachmentUrls.forEach(url => URL.revokeObjectURL(url))
      maskedAttachmentUrls.forEach(url => URL.revokeObjectURL(url))
    }
  }, []) // 빈 의존성 배열: 마운트/언마운트 시에만 실행

  // detectPII는 analyzeWithRAG 내부에서 실행되므로 별도 함수 불필요
  // (초기화 시 호출하던 부분은 제거)

  const analyzeWithRAG = async () => {
    if (!senderContext && !receiverContext) {
      toast.error('수신자 유형을 최소 하나 이상 선택해주세요.')
      return
    }

    if (!originalEmailData) {
      toast.error('원본 이메일 데이터를 불러오는 중입니다.')
      return
    }

    setIsAnalyzing(true)
    setAiSummary('1단계: 이메일 본문에서 PII 추출 중...')

    try {
      // ==================== 1단계: 이메일 본문 PII 추출 ====================
      const emailBody = originalEmailData?.original_body || originalEmailData?.body || ''

      let bodyPIIEntities: DetectedPIIEntity[] = []
      if (emailBody) {
        const bodyResponse = await fetch(`${API_BASE_URL}/api/v1/analyzer/analyze/text`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text_content: emailBody,
            user_request: 'email_analysis'
          })
        })

        if (bodyResponse.ok) {
          const bodyResult: PIIAnalysisResult = await bodyResponse.json()
          bodyPIIEntities = bodyResult.pii_entities || []
          console.log('✅ 이메일 본문 PII:', bodyPIIEntities.length, '개')
        }
      }

      // ==================== 2단계: 첨부파일 PII 추출 ====================
      setAiSummary('2단계: 첨부파일에서 PII 추출 중...')

      let attachmentPIIList: Array<{ filename: string; entities: DetectedPIIEntity[] }> = []

      if (originalEmailData.attachments && originalEmailData.attachments.length > 0) {
        const attachmentPromises = originalEmailData.attachments.map(async (attachment: any) => {
          const filename = attachment.filename

          // Base64 → Blob
          const binaryString = atob(attachment.data)
          const bytes = new Uint8Array(binaryString.length)
          for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i)
          }
          const blob = new Blob([bytes], { type: attachment.content_type })

          // OCR
          const formData = new FormData()
          formData.append('file_content', blob)
          formData.append('file_name', filename)

          const ocrResponse = await fetch(`${API_BASE_URL}/api/v1/ocr/extract/ocr`, {
            method: 'POST',
            body: formData
          })

          if (!ocrResponse.ok) {
            console.error(`❌ OCR 실패: ${filename}`)
            return { filename, entities: [] }
          }

          const ocrResult = await ocrResponse.json()
          const extractedText = typeof ocrResult === 'string' ? ocrResult : ocrResult.full_text || ''

          // PII 분석
          const analysisResponse = await fetch(`${API_BASE_URL}/api/v1/analyzer/analyze/text`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              text_content: extractedText,
              user_request: 'attachment_analysis',
              ocr_data: ocrResult
            })
          })

          if (!analysisResponse.ok) {
            console.error(`❌ PII 분석 실패: ${filename}`)
            return { filename, entities: [] }
          }

          const analysisData: PIIAnalysisResult = await analysisResponse.json()

          return {
            filename,
            entities: analysisData.pii_entities || [],
            ocr_data: ocrResult,
            analysis_data: analysisData
          }
        })

        const attachmentResults = await Promise.all(attachmentPromises)
        attachmentPIIList = attachmentResults

        // 첨부파일 분석 결과를 전역 변수에 저장 (마스킹 시 coordinates 참조용)
        ;(window as any).__attachmentAnalysisResults = attachmentResults

        console.log('✅ 첨부파일 PII:', attachmentResults.reduce((sum, r) => sum + r.entities.length, 0), '개')
      }

// ApproverReviewPage.tsx - 3단계 정규식 PII 검출 부분 수정

// ==================== 3단계: 추가 PII 검출 (중복 제거 강화) ====================
      setAiSummary('3단계: 추가 PII 검출 및 중복 제거 중...')

      // 백엔드에서 이미 검출한 값들 수집 (정확한 문자열 매칭)
      const alreadyDetected = new Set<string>()

      // 본문 PII
      bodyPIIEntities.forEach(entity => {
        alreadyDetected.add(entity.text.trim())
      })

      // 첨부파일 PII
      attachmentPIIList.forEach(fileResult => {
        fileResult.entities.forEach(entity => {
          alreadyDetected.add(entity.text.trim())
        })
      })

      // ✅ 추가: 부분 문자열도 체크 (예: "02-123-4567"이 있으면 "123-4567"은 제외)
      const isSubstringOfDetected = (value: string): boolean => {
        for (const detected of alreadyDetected) {
          if (detected.includes(value) && detected !== value) {
            console.log(`[중복 제거] "${value}"는 "${detected}"의 부분 문자열이므로 제외`)
            return true
          }
        }
        return false
      }

      // 정규식 패턴 (기존)
      const text = (emailData.body || '').replace(/<[^>]*>/g, ' ')
      const patterns = {
        email: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g,
        phone: /\b01[0-9]-?[0-9]{3,4}-?[0-9]{4}\b/g,
        jumin: /\b\d{6}-?[1-4]\d{6}\b/g,
        account: /\b\d{3,4}-?\d{2,6}-?\d{2,7}\b/g,
        passport: /\b[A-Z]\d{8}\b/g,
        driver_license: /\b\d{2}-\d{6,8}-\d{2}\b/g,
        card: /(\d{4})([-. \s])\d{4}\2\d{4}\2\d{4}/g,
      }

      const regexPII: PIIItem[] = []

      for (const [type, regex] of Object.entries(patterns)) {
        const matches = text.match(regex)
        if (matches) {
          matches.forEach((value) => {
            // ✅ 중복 체크 강화
            if (!regexPII.some((item) => item.value === value) && 
                !alreadyDetected.has(value.trim()) &&
                !isSubstringOfDetected(value.trim())) {
              regexPII.push({ type, value })
            } else {
              console.log(`[중복 제거] 정규식 PII 제외: ${value} (이미 검출됨)`)
            }
          })
        }
      }

      console.log('✅ 정규식 PII (중복 완전 제거):', regexPII.length, '개')
      // ==================== 4단계: 모든 PII 통합 (완전 중복 제거) ====================
      setAiSummary('4단계: 모든 PII 통합 중...')

      const allPII: Array<{
        id: string
        type: string
        value: string
        source: 'regex' | 'backend_body' | 'backend_attachment'
        filename?: string
        shouldMask: boolean
        maskingDecision?: MaskingDecision
        coordinate?: PIICoordinate  // 첨부파일 PII의 좌표 정보
        entityIndex?: number  // 원본 entity 인덱스
        start_char?: number
      }> = []

      // 전체 중복 체크용 Set (모든 출처 통합)
      const globalAddedValues = new Set<string>()

      // 정규식 PII
      regexPII.forEach((pii, idx) => {
        const trimmedValue = pii.value.trim()
        if (!globalAddedValues.has(trimmedValue)) {
          globalAddedValues.add(trimmedValue)
          allPII.push({
            id: `regex_${idx}`,
            type: pii.type,
            value: pii.value,
            source: 'regex',
            shouldMask: false, // 기본값: 체크 해제
            maskingDecision: undefined
          })
        }
      })

      // 백엔드 본문 PII (중복 제거)
      bodyPIIEntities.forEach((entity, idx) => {
        const trimmedValue = entity.text.trim()
        // 전역 Set에서 중복 확인
        if (!globalAddedValues.has(trimmedValue)) {
          globalAddedValues.add(trimmedValue)
          allPII.push({
            id: `body_${idx}`,
            type: entity.type,
            value: entity.text,
            source: 'backend_body',
            shouldMask: false,
            maskingDecision: undefined,
            start_char: entity.start_char
          })
        } else {
          console.log(`[중복 제거] 백엔드 본문 PII 제외: ${entity.text} (이미 추가됨)`)
        }
      })

      // 백엔드 첨부파일 PII
      attachmentPIIList.forEach((fileResult) => {
        fileResult.entities.forEach((entity, idx) => {
          // coordinates가 있으면 각 좌표별로 개별 PII 항목 생성
          if (entity.coordinates && entity.coordinates.length > 0) {
            entity.coordinates.forEach((coord: any, coordIdx: number) => {
              allPII.push({
                id: `attachment_${fileResult.filename}_${idx}_coord${coordIdx}`,
                type: entity.type,
                value: entity.text,
                source: 'backend_attachment',
                filename: fileResult.filename,
                shouldMask: false,
                maskingDecision: undefined,
                // 좌표 정보 저장
                coordinate: coord,
                entityIndex: idx
              })
            })
          } else {
            // coordinates가 없으면 기존 방식대로
            allPII.push({
              id: `attachment_${fileResult.filename}_${idx}`,
              type: entity.type,
              value: entity.text,
              source: 'backend_attachment',
              filename: fileResult.filename,
              shouldMask: false,
              maskingDecision: undefined,
              entityIndex: idx
            })
          }
        })
      })

      console.log('📊 통합 PII 목록:', allPII.length, '개')

      // ==================== 5단계: RAG로 마스킹 필요 여부 분석 ====================
      setAiSummary('5단계: AI가 가이드라인을 검색하고 마스킹 필요 여부 분석 중...')
      
      const context: AnalysisContext = {
        sender_type: senderContext,
        receiver_type: receiverContext,
        purpose: purposes,
        regulations: regulations,
      }

      // PII가 없으면 RAG 분석 건너뛰기
      if (allPII.length === 0) {
        toast.info('탐지된 개인정보가 없어 분석을 중단합니다.')
        setAiSummary('탐지된 개인정보가 없습니다.')
        setAllPIIList([])
        setShowPIICheckboxList(false)
        return
      }

      // RAG API 호출 (기존 detectedPII 대신 allPII의 value만 전달)
      const token = localStorage.getItem('auth_token')

      if (!token) {
        throw new Error('인증 정보가 없습니다. 다시 로그인해주세요.')
      }

      console.log('🔑 토큰 확인:', token ? `${token.substring(0, 20)}...` : 'null')

      // 스트리밍 방식으로 변경
      const ragResponse = await fetch(`${API_BASE_URL}/api/vectordb/analyze-stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          email_body: emailData.body,
          email_subject: emailData.subject,
          detected_pii: allPII.map(pii => ({ type: pii.type, value: pii.value })),
          context: context,
          query: `${senderContext} to ${receiverContext} email masking analysis`,
        }),
      })

      if (!ragResponse.ok) {
        const errorData = await ragResponse.json().catch(() => ({}))
        console.error('❌ RAG 분석 실패:', errorData)
        throw new Error(errorData.detail || 'RAG 분석 요청 실패')
      }

      // 스트리밍 응답 처리
      const reader = ragResponse.body?.getReader()
      const decoder = new TextDecoder()
      let decisions: Record<string, MaskingDecision> = {}

      if (reader) {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const chunk = decoder.decode(value)
          const lines = chunk.split('\n\n')

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))

                if (data.type === 'progress') {
                  // 실시간 진행률 업데이트
                  setAnalysisProgress(`${data.current}/${data.total}`)
                } else if (data.type === 'complete') {
                  // 분석 완료
                  decisions = data.data.masking_decisions || {}
                  setMaskingDecisions(decisions)
                  setAiSummary(data.data.summary || '분석이 완료되었습니다.')
                  setAnalysisProgress('') // 완료 후 진행률 초기화
                } else if (data.type === 'error') {
                  throw new Error(data.message)
                }
              } catch (e) {
                console.error('스트림 파싱 오류:', e)
              }
            }
          }
        }
      }

      console.log('📦 분석 완료')

      if (decisions && Object.keys(decisions).length > 0) {

        // ==================== 6단계: RAG 결과를 PII 리스트에 반영 ====================
        // RAG가 마스킹 필요하다고 판단한 PII는 shouldMask = true
        // 백엔드는 pii_0, pii_1, pii_2... 형식의 키를 사용하므로 인덱스 기반 매칭
        let maskCount = 0
        allPII.forEach((pii, index) => {
          const decisionKey = `pii_${index}`
          const matchingDecision = decisions[decisionKey]

          if (matchingDecision) {
            // ✅ pii_id를 저장 (마스킹 시 maskingDecisions 키와 매칭하기 위함)
            (pii as any).pii_id = decisionKey

            // 마스킹 필요 여부에 관계없이 항상 decision 정보 저장
            pii.shouldMask = matchingDecision.should_mask
            pii.maskingDecision = matchingDecision as MaskingDecision

            if (matchingDecision.should_mask) {
              maskCount++
              console.log(`✅ PII ${index} 마스킹 권장:`, pii.value, matchingDecision.reason)
            } else {
              console.log(`⚪ PII ${index} 마스킹 불필요:`, pii.value, matchingDecision.reason)
            }
          } else {
            console.log(`⚠️ PII ${index} 판단 결과 없음:`, pii.value)
          }
        })

        setAllPIIList(allPII)
        setShowPIICheckboxList(true)

        toast.success(`AI 분석 완료! 총 ${allPII.length}개 PII 중 ${maskCount}개 마스킹 권장`)
      } else {
        throw new Error('분석 결과가 올바르지 않습니다.')
      }

    } catch (error) {
      console.error('❌ AI 분석 오류:', error)
      toast.error('AI 분석 중 오류가 발생했습니다.')
      setAiSummary('분석 중 오류가 발생했습니다.')
      setAnalysisProgress('') // 에러 시 진행률 초기화
    } finally {
      setIsAnalyzing(false)
    }
  }

  const maskValue = (value: string, type: string): string => {
    const normalizedType = type.toLowerCase()

    switch (normalizedType) {
      case 'email':
        // 이메일: @와 도메인만 유지, local 부분은 글자수대로 * 처리
        const emailParts = value.split('@')
        if (emailParts.length === 2) {
          const localMasked = '*'.repeat(emailParts[0].length)
          return `${localMasked}@${emailParts[1]}`
        }
        return '*'.repeat(value.length)

      case 'phone':
      case 'phone_number':
        // 전화번호: 지역번호(첫 번째 부분)만 유지, 나머지는 글자수대로 * 처리
        if (value.includes('-')) {
          const phoneParts = value.split('-')
          if (phoneParts.length >= 2) {
            const areaCode = phoneParts[0]
            const maskedParts = phoneParts.slice(1).map(part => '*'.repeat(part.length))
            return [areaCode, ...maskedParts].join('-')
          }
        }
        // 하이픈이 없으면 앞 3자리만 유지
        if (value.length > 3) {
          return value.substring(0, 3) + '*'.repeat(value.length - 3)
        }
        return '*'.repeat(value.length)

      case 'jumin':
      case 'resident_id':
        // 주민등록번호: 하이픈 유지하고 숫자는 글자수대로 * 처리
        if (value.includes('-')) {
          const parts = value.split('-')
          return parts.map(part => '*'.repeat(part.length)).join('-')
        }
        return '*'.repeat(value.length)

      case 'account':
      case 'bank_account':
        // 계좌번호: 하이픈 유지하고 숫자는 글자수대로 * 처리
        if (value.includes('-')) {
          const parts = value.split('-')
          return parts.map(part => '*'.repeat(part.length)).join('-')
        }
        return '*'.repeat(value.length)

      case 'passport':
        // 여권번호: 글자수대로 * 처리
        return '*'.repeat(value.length)

      case 'driver_license':
      case 'drive':
        // 운전면허: 하이픈 유지하고 숫자는 글자수대로 * 처리
        if (value.includes('-')) {
          const parts = value.split('-')
          return parts.map(part => '*'.repeat(part.length)).join('-')
        }
        return '*'.repeat(value.length)

      case 'card':
      case 'card_number':
        // 카드번호: 하이픈/공백/점 유지하고 숫자는 글자수대로 * 처리
        return value.replace(/\d+/g, match => '*'.repeat(match.length))

      case 'person':
      case 'organization':
      case 'location':
        // 개인명, 조직명, 위치: 글자수대로 * 처리
        return '*'.repeat(value.length)

      case 'ip':
        // IP 주소: 점(.) 유지하고 숫자는 글자수대로 * 처리
        if (value.includes('.')) {
          const parts = value.split('.')
          return parts.map(part => '*'.repeat(part.length)).join('.')
        }
        return '*'.repeat(value.length)

      case 'mac':
        // MAC 주소: 콜론(:) 또는 하이픈(-) 유지하고 영숫자는 글자수대로 * 처리
        if (value.includes(':')) {
          const parts = value.split(':')
          return parts.map(part => '*'.repeat(part.length)).join(':')
        } else if (value.includes('-')) {
          const parts = value.split('-')
          return parts.map(part => '*'.repeat(part.length)).join('-')
        }
        return '*'.repeat(value.length)

      case 'gps':
        // GPS: 점(.), 쉼표(,) 유지하고 숫자는 글자수대로 * 처리
        return value.replace(/[\d.]+/g, match => {
          if (match === '.') return '.'
          return '*'.repeat(match.length)
        })

      default:
        // 기본: 글자수대로 * 처리
        return '*'.repeat(value.length)
    }
  }

  const escapeRegex = (str: string): string => {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  }

  const escapeHTML = (str: string): string => {
    const div = document.createElement('div')
    div.textContent = str
    return div.innerHTML
  }

  // 체크박스 토글 핸들러
  const togglePIIMask = (id: string) => {
    setAllPIIList(prev => prev.map(pii =>
      pii.id === id ? { ...pii, shouldMask: !pii.shouldMask } : pii
    ))
  }

  // 마스킹만 실행 (전송은 별도)
  const handleMaskOnly = async () => {
    if (!showPIICheckboxList || allPIIList.length === 0) {
      toast.error('먼저 AI 분석을 실행해주세요.')
      return
    }

    const checkedPIIs = allPIIList.filter(pii => pii.shouldMask)
    if (checkedPIIs.length === 0) {
      toast.error('마스킹할 PII를 선택해주세요.')
      return
    }

    setIsMasking(true)
    toast.loading('마스킹 처리 중...', { id: 'masking-only' })

    // 마스킹 결정 복사본 생성 (실제 마스킹 값으로 업데이트하기 위함)
    const updatedDecisions = { ...maskingDecisions }

    try {
      // ==================== 1단계: 이메일 본문 마스킹 ====================
      // HTML을 텍스트로 변환 (줄바꿈 보존)
      let tempMaskedBody = htmlToText(emailData.body)

      for (const pii of checkedPIIs) {
        if (pii.source === 'regex' || pii.source === 'backend_body') {
          // 프론트엔드 마스킹 규칙 사용
          const masked = maskValue(pii.value, pii.type)
          tempMaskedBody = tempMaskedBody.replace(new RegExp(escapeRegex(pii.value), 'g'), masked)

          // ✅ 실제 마스킹된 값을 decision에 저장
          // pii.pii_id는 "pii_0", "pii_1" 같은 형식 (AI 분석 시 저장됨)
          const piiId = (pii as any).pii_id
          if (piiId && updatedDecisions[piiId]) {
            const oldMaskedValue = updatedDecisions[piiId].masked_value
            updatedDecisions[piiId].masked_value = masked
            console.log(`[마스킹 업데이트] ${piiId} (${pii.type}): "${pii.value}" -> "${masked}" (기존: "${oldMaskedValue}")`)
          } else {
            console.warn(`[마스킹 실패] pii_id=${piiId}, id=${pii.id} - decision을 찾을 수 없음`)
          }
        }
      }

      setMaskedBody(tempMaskedBody)
      setMaskingDecisions(updatedDecisions) // 업데이트된 decision 저장

      // ==================== 2단계: 첨부파일 마스킹 ====================
      const attachmentPIIs = checkedPIIs.filter(pii => pii.source === 'backend_attachment' && pii.filename)

      let tempMaskedAttachments: string[] = []

      if (attachmentPIIs.length > 0) {
        console.log('📎 첨부파일 마스킹 시작:', attachmentPIIs.length, '개 PII')

        // PIIItemFromAnalysis 형식으로 변환 (PDF는 텍스트 검색 방식 사용)
        // 1단계: 전체 PII 리스트(allPIIList)에서 같은 파일+텍스트별로 그룹화
        const groupedAllPIIs = new Map<string, typeof allPIIList>()

        allPIIList.forEach((pii) => {
          if (pii.source === 'backend_attachment' && pii.filename) {
            const key = `${pii.filename}_${pii.value}`
            if (!groupedAllPIIs.has(key)) {
              groupedAllPIIs.set(key, [])
            }
            groupedAllPIIs.get(key)!.push(pii)
          }
        })

        // 2단계: 각 그룹 내에서 Y 좌표 기준으로 정렬 (위에서 아래로)
        groupedAllPIIs.forEach((piis, key) => {
          piis.sort((a, b) => {
            if (a.coordinate && b.coordinate) {
              // Y 좌표 (bbox[1])로 정렬
              return a.coordinate.bbox[1] - b.coordinate.bbox[1]
            }
            return 0
          })
        })

        // 3단계: 선택된 PII들의 instance_index 계산
        const piiItemsForBackend = attachmentPIIs.map((pii) => {
          const key = `${pii.filename}_${pii.value}`
          const group = groupedAllPIIs.get(key) || []
          const instanceIndex = group.findIndex(p => p.id === pii.id)

          // 파일 타입 확인 (확장자 기반)
          const fileExt = pii.filename?.toLowerCase().split('.').pop()
          const isPDF = fileExt === 'pdf'
          const isImage = ['jpg', 'jpeg', 'png', 'gif', 'bmp'].includes(fileExt || '')

          console.log('🔍 PII 처리:', {
            id: pii.id,
            value: pii.value,
            filename: pii.filename,
            fileType: isPDF ? 'PDF' : isImage ? 'Image' : 'Unknown',
            bbox: pii.coordinate?.bbox,
            calculated_instance: instanceIndex
          })

          // coordinate 정보가 이미 PII 객체에 저장되어 있으면 그것을 사용
          if (pii.coordinate) {
            if (isPDF) {
              // PDF: 텍스트 검색 방식 (instance_index 사용)
              console.log(`📄 PDF 마스킹: instance=${instanceIndex}, bbox=${pii.coordinate.bbox}`)
              return {
                filename: pii.filename!,
                pii_type: pii.type,
                text: pii.value,
                pageIndex: pii.coordinate.pageIndex,
                instance_index: instanceIndex  // Y 좌표 기준으로 정렬된 인덱스
              }
            } else if (isImage) {
              // 이미지: bbox 좌표 직접 사용
              console.log(`🖼️ 이미지 마스킹: bbox=${pii.coordinate.bbox}`)
              return {
                filename: pii.filename!,
                pii_type: pii.type,
                text: pii.value,
                pageIndex: pii.coordinate.pageIndex,
                bbox: pii.coordinate.bbox  // bbox 좌표 직접 사용
              }
            } else {
              // 기타: instance_index 사용
              console.log(`📎 기타 파일 마스킹: instance=${instanceIndex}`)
              return {
                filename: pii.filename!,
                pii_type: pii.type,
                text: pii.value,
                pageIndex: pii.coordinate.pageIndex,
                instance_index: instanceIndex
              }
            }
          }

          // coordinate가 없으면 전체 분석 결과에서 찾기 (fallback)
          const fileResult = (window as any).__attachmentAnalysisResults?.find(
            (r: any) => r.filename === pii.filename
          )

          if (!fileResult) {
            console.warn(`⚠️ 파일 분석 결과를 찾을 수 없음: ${pii.filename}`)
            return {
              filename: pii.filename!,
              pii_type: pii.type,
              text: pii.value,
              pageIndex: 0,
              instance_index: instanceIndex
            }
          }

          const entity = fileResult?.analysis_data?.pii_entities?.find(
            (e: any) => e.text === pii.value && e.type === pii.type
          )

          if (entity && entity.coordinates && entity.coordinates.length > 0) {
            // 첫 번째 좌표 사용
            const coord = entity.coordinates[0]
            return {
              filename: pii.filename!,
              pii_type: pii.type,
              text: pii.value,
              pageIndex: coord.pageIndex,
              instance_index: instanceIndex
            }
          }

          return {
            filename: pii.filename!,
            pii_type: pii.type,
            text: pii.value,
            pageIndex: 0,
            instance_index: instanceIndex
          }
        })

        console.log('📤 백엔드로 전송할 PII 항목:', piiItemsForBackend)

        const maskingResponse = await fetch(`${API_BASE_URL}/api/v1/process/masking/pdf`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(piiItemsForBackend)
        })

        if (!maskingResponse.ok) {
          const error = await maskingResponse.json()
          console.error('❌ 첨부파일 마스킹 실패:', error)
          console.error('❌ 실패 상세:', JSON.stringify(error, null, 2))
          throw new Error('첨부파일 마스킹 실패: ' + (error.detail || JSON.stringify(error)))
        }

        const maskingResult = await maskingResponse.json()
        console.log('✅ 첨부파일 마스킹 완료:', maskingResult)

        if (maskingResult.masked_files) {
          tempMaskedAttachments = Object.entries(maskingResult.masked_files)
            .filter(([_, path]) => typeof path === 'string' && path.startsWith('/uploads/masked_'))
            .map(([_, path]) => (path as string).replace('/uploads/', ''))
        }
      }

      setMaskedAttachmentFilenames(tempMaskedAttachments)

      // ==================== 마스킹된 첨부파일 Blob URL 생성 ====================
      // 이전 마스킹된 URL들만 해제 (원본 URL은 유지)
      maskedAttachmentUrls.forEach(url => URL.revokeObjectURL(url))

      const maskedUrlMap = new Map<string, string>()
      for (const maskedFilename of tempMaskedAttachments) {
        try {
          const response = await fetch(`${API_BASE_URL}/uploads/${maskedFilename}`)
          if (response.ok) {
            const blob = await response.blob()
            const url = URL.createObjectURL(blob)
            maskedUrlMap.set(maskedFilename, url)
            console.log(`✅ 마스킹된 파일 URL 생성: ${maskedFilename}`)
          }
        } catch (error) {
          console.error(`❌ 마스킹된 파일 로드 실패: ${maskedFilename}`, error)
        }
      }
      setMaskedAttachmentUrls(maskedUrlMap)
      setShowMaskedPreview(true)

      toast.dismiss('masking-only')
      toast.success(`마스킹 완료! (본문: ${checkedPIIs.length - attachmentPIIs.length}개, 첨부파일: ${attachmentPIIs.length}개)`)

      // ==================== 3단계: MongoDB 저장 ====================
      if (emailData.email_id) {
        try {
          console.log('📤 마스킹된 이메일 저장 요청:', {
            email_id: emailData.email_id,
            masked_attachment_count: tempMaskedAttachments.length,
            pii_masked_count: checkedPIIs.length
          })

          // 원본 첨부파일 이름 추출
          const originalAttachmentFilenames = emailData.attachments.map((att) =>
            att instanceof File ? att.name : att.filename || ''
          ).filter(Boolean)

          const saveMaskedResponse = await fetch(`${API_BASE_URL}/api/v1/process/masking/save-masked-email`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              email_id: emailData.email_id,
              from_email: emailData.from,
              to_emails: emailData.to,
              subject: emailData.subject,
              masked_body: tempMaskedBody,
              masked_attachment_filenames: tempMaskedAttachments,
              original_attachment_filenames: originalAttachmentFilenames,  // 원본 첨부파일 추가
              masking_decisions: updatedDecisions, // ✅ 업데이트된 decision 사용
              pii_masked_count: checkedPIIs.length
            })
          })

          if (saveMaskedResponse.ok) {
            const saveResult = await saveMaskedResponse.json()
            console.log('✅ 마스킹된 이메일 MongoDB 저장 성공:', saveResult)
            toast.success('마스킹된 이메일이 MongoDB에 저장되었습니다!')
          } else {
            const errorData = await saveMaskedResponse.json()
            console.error('⚠️ 마스킹된 이메일 저장 실패:', errorData)
            toast.warning('마스킹은 완료되었지만 MongoDB 저장에 실패했습니다.')
          }
        } catch (saveError) {
          console.error('⚠️ 마스킹된 이메일 저장 중 오류:', saveError)
          toast.warning('마스킹은 완료되었지만 MongoDB 저장에 실패했습니다.')
        }
      } else {
        console.warn('⚠️ email_id가 없어서 마스킹된 이메일을 저장하지 못했습니다.')
      }

    } catch (error: any) {
      toast.dismiss('masking-only')
      console.error('❌ 마스킹 오류:', error)
      toast.error(`마스킹 실패: ${error.message}`)
    } finally {
      setIsMasking(false)
    }
  }

  // 마스킹 적용 및 전송
  const handleSendMaskedEmail = async () => {
    setIsSending(true)
    toast.loading('이메일 전송 준비 중...', { id: 'sending-email' })

    try {
      // ==================== 1단계: 마스킹된 이메일 MongoDB 저장 ====================
      if (emailData.email_id && showMaskedPreview) {
        try {
          console.log('📤 마스킹된 이메일 저장 요청:', {
            email_id: emailData.email_id,
            masked_attachment_count: maskedAttachmentFilenames.length,
          })

          // 원본 첨부파일 이름 추출
          const originalAttachmentFilenames = emailData.attachments.map((att) =>
            att instanceof File ? att.name : att.filename || ''
          ).filter(Boolean)

          console.log('⏳ MongoDB 저장 시작...')
          toast.loading('마스킹된 이메일 저장 중...', { id: 'sending-email' })

          const saveMaskedResponse = await fetch(`${API_BASE_URL}/api/v1/process/masking/save-masked-email`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              email_id: emailData.email_id,
              from_email: emailData.from,
              to_emails: emailData.to,
              subject: emailData.subject,
              masked_body: maskedBody,
              masked_attachment_filenames: maskedAttachmentFilenames,
              original_attachment_filenames: originalAttachmentFilenames,
              masking_decisions: maskingDecisions,
              pii_masked_count: allPIIList.filter(p => p.shouldMask).length
            })
          })

          if (!saveMaskedResponse.ok) {
            const errorData = await saveMaskedResponse.json()
            console.error('⚠️ 마스킹된 이메일 저장 실패:', errorData)
            toast.warning('마스킹 데이터 저장에 실패했습니다. 원본으로 전송합니다.', { id: 'sending-email' })
            // 저장 실패해도 계속 진행 (원본으로 전송)
          } else {
            const saveResult = await saveMaskedResponse.json()
            console.log('✅ 마스킹된 이메일 MongoDB 저장 성공:', saveResult)
            
            // ✅ 저장 완료 후 짧은 대기 시간 (MongoDB 인덱싱 대기)
            console.log('⏳ MongoDB 인덱싱 대기 중... (500ms)')
            await new Promise(resolve => setTimeout(resolve, 500))
            console.log('✅ 대기 완료, SMTP 전송 시작')
          }
        } catch (saveError) {
          console.error('⚠️ 마스킹된 이메일 저장 중 오류:', saveError)
          toast.warning('마스킹 데이터 저장에 실패했습니다. 원본으로 전송합니다.', { id: 'sending-email' })
        }
      }

      // ==================== 2단계: 이메일 전송 ====================
      toast.loading('이메일 전송 중...', { id: 'sending-email' })

      const token = localStorage.getItem('auth_token')

      if (!token) {
        throw new Error('인증이 필요합니다. 다시 로그인해주세요.')
      }

      console.log('📧 SMTP 전송 요청 시작')
      console.log('  masked_email_id:', emailData.email_id)
      console.log('  use_masked_email:', showMaskedPreview)

      // 본문: 마스킹된 본문이 있으면 사용, 없으면 원본 사용
      const bodyToSend = maskedBody || emailData.body
      const bodyHtml = bodyToSend.replace(/\n/g, '<br>')

      // SMTP 전송
      const smtpResponse = await fetch(`${API_BASE_URL}/api/v1/smtp/send`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          masked_email_id: showMaskedPreview ? emailData.email_id : undefined,
          from_email: emailData.from,
          to: emailData.to.join(','),
          subject: emailData.subject,
          body: bodyHtml,
          use_masked_email: showMaskedPreview,
        }),
      })

      toast.dismiss('sending-email')

      if (!smtpResponse.ok) {
        const smtpError = await smtpResponse.json()
        console.error('❌ SMTP 전송 실패:', smtpError)
        throw new Error(smtpError.detail || 'SMTP 전송 실패')
      }

      const result = await smtpResponse.json()
      console.log('✅ SMTP 전송 성공:', result)

      toast.success('이메일 전송 완료!')

      if (onSendComplete) {
        onSendComplete()
      }
    } catch (error: any) {
      toast.dismiss('sending-email')
      console.error('❌ 이메일 전송 오류:', error)
      toast.error(`전송 실패: ${error.message}`)
    } finally {
      setIsSending(false)
    }
  }

  const typeNames: Record<string, string> = {
    EMAIL: '이메일',
    GPS: 'GPS',
    MAC: 'MAC 주소',
    RESIDENT_ID: '주민등록번호',
    PASSPORT: '여권번호',
    DRIVE: '운전면허번호',
    PHONE: '전화번호',
    BANK_ACCOUNT: '계좌 번호',
    CARD_NUMBER: '카드 번호',
    IP: 'IP 주소',
    PERSON: '개인명',
    LOCATION: '위치 정보',
    ORGANIZATION: '조직명',

    // 정규식 엔티티 (영어 소문자) ✨ 추가
    email: '이메일',
    phone: '전화번호',
    jumin: '주민등록번호',
    account: '계좌번호',
    passport: '여권번호',
    card: '카드 번호',
    driver_license: '운전면허번호',
  }

  // 첨부파일 렌더링 (MongoDB 데이터 사용)
  const renderAttachment = (attachment: AttachmentInfo | any) => {
    // filename을 키로 사용 (MongoDB 데이터의 경우)
    const url = attachmentUrls.get(attachment.filename) || attachmentUrls.get(attachment.file_id)

    if (!url) {
      console.log('첨부파일 URL 없음:', attachment.filename, 'Available keys:', Array.from(attachmentUrls.keys()))
      return <div className="text-sm text-gray-500">로딩 중...</div>
    }

    const isImage = attachment.content_type.startsWith('image/')
    const isPDF = attachment.content_type === 'application/pdf'

    if (isImage) {
      return (
        <img
          src={url}
          alt={`${attachment.filename} 미리보기`}
          className="max-w-full h-auto border rounded"
        />
      )
    } else if (isPDF) {
      return (
        <object
          data={url}
          type="application/pdf"
          className="w-full h-[600px] border rounded"
        >
          <p className="text-sm text-gray-500">
            PDF를 표시할 수 없습니다.
            <a href={url} download={attachment.filename} className="text-blue-500 underline ml-1">
              다운로드
            </a>
          </p>
        </object>
      )
    }

    return (
      <div className="p-4 border rounded bg-gray-50">
        <p className="text-sm">📄 {attachment.filename}</p>
        <a href={url} download={attachment.filename} className="text-blue-500 text-sm underline">
          다운로드
        </a>
      </div>
    )
  }

  return (
    <>
      <style>{scrollbarHideStyle}</style>
      <div className="flex h-screen overflow-hidden">
        {/* 중앙: 이메일 내용 (스크롤 가능) */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden scrollbar-hide p-6 space-y-6" style={{ scrollbarWidth: 'none', msOverflowStyle: 'none', minWidth: 0 }}>
          {/* 헤더 */}
          <div className="mb-6">
            <h2 className="text-2xl font-semibold">이메일 마스킹 검토</h2>
            <p className="text-muted-foreground text-sm mt-1">AI가 분석한 개인정보를 확인하고 마스킹을 적용하세요</p>
          </div>

          {/* 원본 이메일 데이터 (MongoDB) */}
          {originalEmailData && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">원본 이메일 정보</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="bg-muted/30 p-4 rounded-lg">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                      <label className="font-medium text-foreground">발신자</label>
                      <p className="text-muted-foreground mt-1">{originalEmailData.from_email}</p>
                    </div>
                    <div>
                      <label className="font-medium text-foreground">수신자</label>
                      <p className="text-muted-foreground mt-1">{originalEmailData.to_emails?.join(', ')}</p>
                    </div>
                    <div className="md:col-span-2">
                      <label className="font-medium text-foreground">제목</label>
                      <p className="text-muted-foreground mt-1">{originalEmailData.subject}</p>
                    </div>
                    <div>
                      <label className="font-medium text-foreground">저장 시간</label>
                      <p className="text-muted-foreground mt-1">
                        {new Date(originalEmailData.created_at).toLocaleString('ko-KR')}
                      </p>
                    </div>
                  </div>

                  {originalEmailData.attachments && originalEmailData.attachments.length > 0 && (
                    <div className="mt-4 pt-4 border-t">
                      <label className="font-medium text-foreground text-sm">
                        첨부파일 ({originalEmailData.attachments.length}개)
                      </label>
                      <div className="mt-2 space-y-2">
                        {originalEmailData.attachments.map((att: any, idx: number) => (
                          <div key={idx} className="flex items-center gap-2 p-2 bg-background rounded text-sm border">
                            <span className="font-medium flex-1">{att.filename}</span>
                            <Badge variant="outline" className="text-xs">{att.content_type}</Badge>
                            <span className="text-muted-foreground text-xs">
                              {(att.size / 1024).toFixed(2)} KB
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {isLoadingOriginal && (
            <Card>
              <CardContent className="p-6 text-center text-muted-foreground">
                <div className="flex items-center justify-center gap-2">
                  <div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full"></div>
                  원본 이메일 데이터를 불러오는 중...
                </div>
              </CardContent>
            </Card>
          )}

          {/* 이메일 내용 */}
          <Card>
            <CardContent className="min-h-[400px] pt-6">
              <div className="space-y-6">
                {/* 이메일 본문 (contenteditable) */}
                <div>
                  <h4 className="font-medium mb-2">📧 메일 본문</h4>
                  <div
                    ref={emailBodyRef}
                    contentEditable
                    suppressContentEditableWarning
                    className="border rounded p-4 min-h-[200px] focus:outline-none focus:ring-2 focus:ring-blue-500"
                    style={{ whiteSpace: 'pre-wrap' }}
                    dangerouslySetInnerHTML={{ __html: emailData.body || '' }}
                  />
                </div>

                {/* 첨부파일 표시 */}
                {(originalEmailData?.attachments || emailData.attachments).map((att: any, idx: number) => (
                  <div key={att.filename || att.file_id || idx} className="border-t pt-4">
                    <h4 className="font-medium mb-2">📎 {att.filename}</h4>
                    {renderAttachment(att)}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>


          {/* 마스킹 미리보기 */}
          {showMaskedPreview && (
            <Card className="border-green-600">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <span className="text-green-600">✓</span> 마스킹 완료
                </CardTitle>
                <CardDescription>
                  마스킹된 결과를 확인하고 이메일을 전송하세요
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* 마스킹된 본문 */}
                <div>
                  <label className="font-medium text-sm mb-2 block">마스킹된 본문</label>
                  <div className="bg-muted/50 border rounded-lg p-4 text-sm whitespace-pre-wrap">
                    {maskedBody || '본문이 없습니다'}
                  </div>
                </div>

                {/* 전송될 첨부파일 (원본 + 마스킹) */}
                {(originalEmailData?.attachments || emailData.attachments).length > 0 && (
                  <div>
                    <label className="font-medium text-sm mb-2 block">
                      전송될 첨부파일 ({(originalEmailData?.attachments || emailData.attachments).length}개)
                    </label>
                    <div className="space-y-3">
                      {(originalEmailData?.attachments || emailData.attachments).map((att: any, idx: number) => {
                        const originalFilename = att.filename || (att instanceof File ? att.name : '')

                        // 마스킹된 파일이 있는지 확인
                        const maskedFilename = maskedAttachmentFilenames.find(masked =>
                          masked === `masked_${originalFilename}`
                        )

                        // 마스킹된 파일이 있으면 마스킹 URL, 없으면 원본 URL 사용
                        const url = maskedFilename
                          ? maskedAttachmentUrls.get(maskedFilename)
                          : attachmentUrls.get(originalFilename)

                        const displayFilename = maskedFilename || originalFilename
                        const isMasked = !!maskedFilename
                        const isImage = displayFilename.toLowerCase().match(/\.(jpg|jpeg|png|gif)$/)
                        const isPDF = displayFilename.toLowerCase().endsWith('.pdf')

                        return (
                          <div key={idx} className="bg-white border rounded p-3">
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-sm">{displayFilename}</span>
                                {isMasked ? (
                                  <Badge variant="default" className="text-xs bg-green-600">마스킹됨</Badge>
                                ) : (
                                  <Badge variant="outline" className="text-xs">원본</Badge>
                                )}
                              </div>
                              {url && (
                                <a
                                  href={url}
                                  download={displayFilename}
                                  className="text-blue-500 text-xs underline"
                                >
                                  다운로드
                                </a>
                              )}
                            </div>

                            {url && isImage && (
                              <img
                                src={url}
                                alt={displayFilename}
                                className="max-w-full h-auto border rounded"
                              />
                            )}

                            {url && isPDF && (
                              <object
                                data={url}
                                type="application/pdf"
                                className="w-full h-[800px] border rounded"
                              >
                                <p className="text-sm text-gray-500">
                                  PDF를 표시할 수 없습니다.
                                </p>
                              </object>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* 전송 버튼 */}
          <Button
            onClick={handleSendMaskedEmail}
            disabled={isSending}
            className="w-full"
            size="lg"
          >
            <Send className="mr-2 h-4 w-4" />
            {isSending ? '전송 중...' : showMaskedPreview ? '마스킹된 이메일 전송' : '이메일 전송'}
          </Button>
        </div>

        {/* 우측: 컨텍스트 설정 (스크롤 가능, 고정 너비) */}
      <div className="w-[400px] flex-shrink-0 overflow-y-auto scrollbar-hide border-l bg-muted/10" style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
        <div className="p-6 space-y-6">
          {/* 헤더 높이만큼 공백 */}
          <div className="h-[52px]"></div>
          <Card>
            <CardContent className="space-y-4 pt-6">
              {/* 사내 그룹 */}
              <div className="border-b pb-4">
                <div className="text-sm font-medium mb-3">
                  <span>사내</span>
                </div>
                <div className="space-y-2 pl-2">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={purposes.includes('인사팀(HR)')}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setPurposes([...purposes, '인사팀(HR)'])
                          setSenderContext('사내')
                        } else {
                          setPurposes(purposes.filter((p) => p !== '인사팀(HR)'))
                          // 사내 항목이 모두 해제되면 senderContext 초기화
                          if (!purposes.some(p => ['고객지원팀(CS)', 'R&D팀', '대외협력팀'].includes(p))) {
                            setSenderContext('')
                          }
                        }
                      }}
                    />
                    <span className="text-sm">인사팀(HR)</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={purposes.includes('고객지원팀(CS)')}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setPurposes([...purposes, '고객지원팀(CS)'])
                          setSenderContext('사내')
                        } else {
                          setPurposes(purposes.filter((p) => p !== '고객지원팀(CS)'))
                          if (!purposes.some(p => ['인사팀(HR)', 'R&D팀', '대외협력팀'].includes(p))) {
                            setSenderContext('')
                          }
                        }
                      }}
                    />
                    <span className="text-sm">고객지원팀(CS)</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={purposes.includes('R&D팀')}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setPurposes([...purposes, 'R&D팀'])
                          setSenderContext('사내')
                        } else {
                          setPurposes(purposes.filter((p) => p !== 'R&D팀'))
                          if (!purposes.some(p => ['인사팀(HR)', '고객지원팀(CS)', '대외협력팀'].includes(p))) {
                            setSenderContext('')
                          }
                        }
                      }}
                    />
                    <span className="text-sm">R&D팀</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={purposes.includes('대외협력팀')}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setPurposes([...purposes, '대외협력팀'])
                          setSenderContext('사내')
                        } else {
                          setPurposes(purposes.filter((p) => p !== '대외협력팀'))
                          if (!purposes.some(p => ['인사팀(HR)', '고객지원팀(CS)', 'R&D팀'].includes(p))) {
                            setSenderContext('')
                          }
                        }
                      }}
                    />
                    <span className="text-sm">대외협력팀</span>
                  </label>
                </div>
              </div>

              {/* 사외 그룹 */}
              <div className="border-b pb-4">
                <div className="text-sm font-medium mb-3">
                  <span>사외</span>
                </div>
                <div className="space-y-2 pl-2">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={purposes.includes('협력 업체')}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setPurposes([...purposes, '협력 업체'])
                          setReceiverContext('사외')
                        } else {
                          setPurposes(purposes.filter((p) => p !== '협력 업체'))
                          if (!purposes.some(p => ['고객사', '정부 기관'].includes(p))) {
                            setReceiverContext('')
                          }
                        }
                      }}
                    />
                    <span className="text-sm">협력 업체</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={purposes.includes('고객사')}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setPurposes([...purposes, '고객사'])
                          setReceiverContext('사외')
                        } else {
                          setPurposes(purposes.filter((p) => p !== '고객사'))
                          if (!purposes.some(p => ['협력 업체', '정부 기관'].includes(p))) {
                            setReceiverContext('')
                          }
                        }
                      }}
                    />
                    <span className="text-sm">고객사</span>
                  </label>

                  {/* 정부 기관 (서브 드롭다운) */}
                  <div>
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={purposes.includes('정부 기관')}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setPurposes([...purposes, '정부 기관'])
                            setReceiverContext('사외')
                          } else {
                            setPurposes(purposes.filter((p) => p !== '정부 기관'))
                            if (!purposes.some(p => ['협력 업체', '고객사'].includes(p))) {
                              setReceiverContext('')
                            }
                          }
                        }}
                      />
                      <span className="text-sm">정부 기관</span>
                    </label>
                    {purposes.includes('정부 기관') && (
                      <div className="ml-6 mt-2 space-y-2 border-l-2 border-gray-200 pl-3">
                        <label className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={purposes.includes('세무 신고 / 재무 보고')}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setPurposes([...purposes, '세무 신고 / 재무 보고'])
                              } else {
                                setPurposes(purposes.filter((p) => p !== '세무 신고 / 재무 보고'))
                              }
                            }}
                          />
                          <span className="text-sm">세무 신고 / 재무 보고</span>
                        </label>
                        <label className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={purposes.includes('노동·고용 관련 보고')}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setPurposes([...purposes, '노동·고용 관련 보고'])
                              } else {
                                setPurposes(purposes.filter((p) => p !== '노동·고용 관련 보고'))
                              }
                            }}
                          />
                          <span className="text-sm">노동·고용 관련 보고</span>
                        </label>
                        <label className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={purposes.includes('개인정보·보안 규제 대응')}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setPurposes([...purposes, '개인정보·보안 규제 대응'])
                              } else {
                                setPurposes(purposes.filter((p) => p !== '개인정보·보안 규제 대응'))
                              }
                            }}
                          />
                          <span className="text-sm">개인정보·보안 규제 대응</span>
                        </label>
                        <label className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={purposes.includes('정부 지원사업 / 과제 보고')}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setPurposes([...purposes, '정부 지원사업 / 과제 보고'])
                              } else {
                                setPurposes(purposes.filter((p) => p !== '정부 지원사업 / 과제 보고'))
                              }
                            }}
                          />
                          <span className="text-sm">정부 지원사업 / 과제 보고</span>
                        </label>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* 세부 커스텀 그룹 */}
              <div className="pb-4">
                <div className="text-sm font-medium mb-3">
                  <span>세부 커스텀</span>
                </div>
                <div className="space-y-2 pl-2">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={regulations.includes('사내 규칙 우선')}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setRegulations([...regulations, '사내 규칙 우선'])
                        } else {
                          setRegulations(regulations.filter((r) => r !== '사내 규칙 우선'))
                        }
                      }}
                    />
                    <span className="text-sm">사내 규칙 우선</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={regulations.includes('국내 법률 우선')}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setRegulations([...regulations, '국내 법률 우선'])
                        } else {
                          setRegulations(regulations.filter((r) => r !== '국내 법률 우선'))
                        }
                      }}
                    />
                    <span className="text-sm">국내 법률 우선</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={regulations.includes('GDPR 우선')}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setRegulations([...regulations, 'GDPR 우선'])
                        } else {
                          setRegulations(regulations.filter((r) => r !== 'GDPR 우선'))
                        }
                      }}
                    />
                    <span className="text-sm">GDPR 우선</span>
                  </label>
                </div>
              </div>

              <div className="pt-4 space-y-2">
                <Button onClick={analyzeWithRAG} disabled={isAnalyzing} className="w-full">
                  {isAnalyzing ? 'AI 분석 중...' : 'AI 분석 시작'}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* AI 분석 진행 상황 */}
          {isAnalyzing && (
            <Card className="border-primary">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full"></div>
                  AI 분석 진행 중
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground">{aiSummary}</p>
                {analysisProgress && (
                  <div className="mt-2 p-2 bg-muted/50 rounded text-center">
                    <span className="text-lg font-mono font-semibold text-primary">{analysisProgress}</span>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* AI 분석 요약 (완료 후) */}
          {!isAnalyzing && showPIICheckboxList && (
            <Card className="border-green-600">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <span className="text-green-600">✓</span> AI 분석 완료
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{aiSummary}</p>
              </CardContent>
            </Card>
          )}

          {/* PII 체크박스 리스트 (AI 분석 완료 후 표시) */}
          {showPIICheckboxList && allPIIList.length > 0 && (
            <Card className="border-primary">
              <CardHeader>
                <CardTitle className="flex items-center justify-between text-base">
                  <span>마스킹 대상 PII</span>
                  <Badge variant="secondary" className="text-xs font-normal">
                    선택: {allPIIList.filter(p => p.shouldMask).length} / {allPIIList.length}
                  </Badge>
                </CardTitle>
                <CardDescription className="text-sm">
                  AI가 권장한 항목은 체크되어 있습니다
                </CardDescription>
              </CardHeader>
              <CardContent>
                {allPIIList.length === 0 ? (
                  <div className="text-center py-8 text-sm text-muted-foreground">
                    검출된 PII가 없습니다
                  </div>
                ) : (
                  <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
                    {allPIIList.map((pii) => (
                    <div
                      key={pii.id}
                      className={`p-3 border rounded-lg transition-all ${
                        pii.shouldMask
                          ? 'bg-amber-50 border-amber-300'
                          : 'bg-background border-border'
                      }`}
                    >
                      <div className="flex items-start gap-2">
                        {/* 체크박스 */}
                        <input
                          type="checkbox"
                          checked={pii.shouldMask}
                          onChange={() => togglePIIMask(pii.id)}
                          className="mt-1 h-4 w-4 cursor-pointer"
                        />

                        {/* PII 정보 */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1 mb-1 flex-wrap">
                            <Badge variant="outline" className="text-xs">
                              {typeNames[pii.type] || pii.type}
                            </Badge>
                            {/* 출처 표시 */}
                            {pii.source === 'backend_body' && (
                              <Badge variant="secondary" className="text-xs bg-blue-100 text-blue-700">
                                📝 본문
                              </Badge>
                            )}
                            {pii.source === 'regex' && (
                              <Badge variant="secondary" className="text-xs bg-blue-100 text-blue-700">
                                📝 본문
                              </Badge>
                            )}
                            {pii.source === 'backend_attachment' && pii.filename && (
                              <Badge variant="secondary" className="text-xs bg-green-100 text-green-700">
                                📎 {pii.filename}
                              </Badge>
                            )}
                            {pii.shouldMask && pii.maskingDecision?.risk_level && (
                              <Badge
                                variant={pii.maskingDecision.risk_level === 'high' ? 'destructive' : 'default'}
                                className="text-xs"
                              >
                                {pii.maskingDecision.risk_level}
                              </Badge>
                            )}
                          </div>

                          {/* PII 값 */}
                          <div className="font-mono text-xs bg-gray-100 p-1.5 rounded border mb-1 break-all">
                            {pii.value}
                            {pii.shouldMask && (
                              <div className="text-green-600 mt-1">
                                → {maskValue(pii.value, pii.type)}
                              </div>
                            )}
                          </div>

                          {/* AI 분석 근거 (모든 경우 표시) */}
                          {pii.maskingDecision && (
                            <div className="text-xs space-y-1">
                              <p className="text-muted-foreground">
                                💡 {pii.maskingDecision.reason}
                              </p>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                    ))}
                  </div>
                )}

                {/* 전체 선택/해제 버튼 */}
                <div className="flex gap-2 mt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={() => {
                      setAllPIIList(prev => prev.map(pii => ({ ...pii, shouldMask: true })))
                    }}
                  >
                    전체 선택
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={() => {
                      setAllPIIList(prev => prev.map(pii => ({ ...pii, shouldMask: false })))
                    }}
                  >
                    전체 해제
                  </Button>
                </div>

                {/* 마스킹 실행 버튼 */}
                <div className="mt-4 space-y-2">
                  <Button
                    onClick={handleMaskOnly}
                    disabled={isMasking || allPIIList.filter(p => p.shouldMask).length === 0}
                    className="w-full"
                    size="lg"
                  >
                    {isMasking ? '마스킹 처리 중...' : `선택된 PII 마스킹 (${allPIIList.filter(p => p.shouldMask).length}개)`}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
        </div>
      </div>
    </>
  )
}