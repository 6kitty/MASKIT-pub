import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import {
  ArrowLeft,
  Mail,
  Paperclip,
  Download,
  User,
  Calendar,
  Clock,
  CheckCircle,
  XCircle,
} from 'lucide-react'

interface EmailDetail {
  _id: string
  from_email: string
  to_email: string
  subject: string
  body?: string
  original_body?: string
  masked_body?: string
  status?: 'pending' | 'approved' | 'rejected'
  created_at: string
  sent_at?: string
  read_at?: string
  attachments?: Array<{
    file_id?: string
    filename: string
    size: number
    content_type: string
  }>
  masking_decisions?: Record<string, any>
}

interface ReceivedDetailPageProps {
  emailId: string
  onBack: () => void
}

export function ReceivedDetailPage({ emailId, onBack }: ReceivedDetailPageProps) {
  const [email, setEmail] = useState<EmailDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadEmailDetail()
  }, [emailId])

  const loadEmailDetail = async () => {
    try {
      setLoading(true)
      const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
      const { authenticatedFetch } = await import('../utils/auth')
      const data = await authenticatedFetch(`${API_BASE}/api/v1/emails/email/${emailId}`)
      setEmail(data)
      setError(null)
    } catch (err) {
      console.error('Error loading email detail:', err)
      setError(err instanceof Error ? err.message : '오류가 발생했습니다.')
    } finally {
      setLoading(false)
    }
  }

  const getStatusBadge = (status?: string) => {
    if (!status) return null
    const variants = {
      pending: { variant: 'secondary' as const, icon: Clock },
      approved: { variant: 'default' as const, icon: CheckCircle },
      rejected: { variant: 'destructive' as const, icon: XCircle },
    }
    const config = variants[status as keyof typeof variants] || variants.pending
    const Icon = config.icon
    return (
      <Badge variant={config.variant} className="gap-1">
        <Icon className="h-3 w-3" />
      </Badge>
    )
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'Asia/Seoul'
    })
  }

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
  }

  const handleDownloadAttachment = async (fileId: string | undefined, filename: string) => {
    try {
      const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
      const token = localStorage.getItem('auth_token')
      let downloadUrl: string

      // fileId가 있으면 GridFS 다운로드 (기존 방식)
      // fileId가 없으면 filename으로 MongoDB Base64 다운로드 (SMTP로 전송된 이메일)
      if (fileId) {
        downloadUrl = `${API_BASE}/api/v1/emails/email/${emailId}/attachments/${fileId}`
      } else {
        downloadUrl = `${API_BASE}/api/v1/emails/email/${emailId}/attachments/by-filename/${encodeURIComponent(filename)}`
      }

      const response = await fetch(downloadUrl, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      if (!response.ok) {
        throw new Error('파일 다운로드에 실패했습니다.')
      }

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err) {
      console.error('Error downloading attachment:', err)
      alert(err instanceof Error ? err.message : '파일 다운로드 중 오류가 발생했습니다.')
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={onBack}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          뒤로 가기
        </Button>
        <Card>
          <CardContent className="pt-6">
            <p className="text-center text-muted-foreground">메일을 불러오는 중...</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (error || !email) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={onBack}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          뒤로 가기
        </Button>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <p className="text-red-800">{error || '메일을 찾을 수 없습니다.'}</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <Button variant="ghost" onClick={onBack}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          뒤로 가기
        </Button>
        {email.status && getStatusBadge(email.status)}
      </div>

      {/* 메일 정보 */}
      <Card>
        <CardHeader className="space-y-3">
          <CardTitle className="text-2xl">{email.subject}</CardTitle>
          <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <User className="h-4 w-4" />
              <span>{email.from_email}</span>
            </div>
            <Separator orientation="vertical" className="h-4" />
            <div className="flex items-center gap-2">
              <Mail className="h-4 w-4" />
              <span>{email.to_email}</span>
            </div>
            <Separator orientation="vertical" className="h-4" />
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4" />
              <span>{formatDate(email.created_at)}</span>
            </div>
          </div>
        </CardHeader>
        <Separator />
        <CardContent className="pt-6 space-y-6">
          {/* 메일 본문 */}
          <div>
            <div className="prose prose-sm max-w-none dark:prose-invert">
              <div
                className="text-sm leading-relaxed"
                dangerouslySetInnerHTML={{
                  __html: email.masked_body || email.original_body || email.body || '본문 없음'
                }}
              />
            </div>
          </div>

          {/* 첨부파일 */}
          {email.attachments && email.attachments.length > 0 && (
            <>
              <Separator />
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <Paperclip className="h-5 w-5 text-muted-foreground" />
                  <h3 className="text-lg font-semibold">
                    첨부파일 ({email.attachments.length}개)
                  </h3>
                </div>
                <div className="grid gap-3">
                  {email.attachments.map((attachment, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between p-4 border rounded-lg hover:bg-accent/50 transition-colors group"
                    >
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <div className="p-2 rounded-md bg-primary/10">
                          <Paperclip className="h-4 w-4 text-primary" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{attachment.filename}</p>
                          <p className="text-xs text-muted-foreground">
                            {formatFileSize(attachment.size)} • {attachment.content_type}
                          </p>
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="ml-4 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() => handleDownloadAttachment(attachment.file_id, attachment.filename)}
                      >
                        <Download className="h-4 w-4 mr-2" />
                        다운로드
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* 추가 메타 정보 */}
          {(email.sent_at || email.read_at) && (
            <>
              <Separator />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                {email.sent_at && (
                  <div className="flex items-start gap-2">
                    <CheckCircle className="h-4 w-4 text-muted-foreground mt-0.5" />
                    <div>
                      <p className="font-medium">전송일</p>
                      <p className="text-muted-foreground">{formatDate(email.sent_at)}</p>
                    </div>
                  </div>
                )}
                {email.read_at && (
                  <div className="flex items-start gap-2">
                    <Mail className="h-4 w-4 text-muted-foreground mt-0.5" />
                    <div>
                      <p className="font-medium">읽은 날짜</p>
                      <p className="text-muted-foreground">{formatDate(email.read_at)}</p>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}