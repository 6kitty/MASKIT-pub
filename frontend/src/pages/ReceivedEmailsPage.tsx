import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Mail, Paperclip, ArrowLeft, Inbox, Search, Filter } from 'lucide-react'

interface Email {
  _id: string
  subject: string
  from_email: string
  created_at: string
  attachments?: any[]
  read?: boolean
}

interface ReceivedEmailsPageProps {
  onNavigate?: (view: string, emailId?: string) => void
  onBack?: () => void
}

export function ReceivedEmailsPage({ onNavigate, onBack }: ReceivedEmailsPageProps) {
  const [emails, setEmails] = useState<Email[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [dateFilter, setDateFilter] = useState<string>('all')
  const [readFilter, setReadFilter] = useState<string>('all')

  useEffect(() => {
    loadReceivedEmails()
  }, [])

  const loadReceivedEmails = async () => {
    try {
      setLoading(true)
      const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
      const token = localStorage.getItem('auth_token')

      if (!token) {
        throw new Error('인증 토큰이 없습니다.')
      }

      // 받은 메일함 API 엔드포인트 (백엔드에 구현 필요)
      const response = await fetch(`${API_BASE}/api/v1/emails/received-emails`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      if (!response.ok) {
        throw new Error('메일을 불러오는데 실패했습니다.')
      }

      const data = await response.json()
      setEmails(data)
      setError(null)
    } catch (err) {
      console.error('Error loading received emails:', err)
      setError(err instanceof Error ? err.message : '오류가 발생했습니다.')
    } finally {
      setLoading(false)
    }
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

  // 필터링된 메일 목록
  const filteredEmails = emails.filter((email) => {
    const matchesSearch =
      email.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
      email.from_email.toLowerCase().includes(searchQuery.toLowerCase())

    // 날짜 필터링
    if (dateFilter !== 'all') {
      const emailDate = new Date(email.created_at)
      const now = new Date()
      const daysDiff = Math.floor((now.getTime() - emailDate.getTime()) / (1000 * 60 * 60 * 24))

      if (dateFilter === 'today' && daysDiff > 0) return false
      if (dateFilter === 'week' && daysDiff > 7) return false
      if (dateFilter === 'month' && daysDiff > 30) return false
    }

    const matchesRead =
      readFilter === 'all' ||
      (readFilter === 'read' && email.read) ||
      (readFilter === 'unread' && !email.read)
    return matchesSearch && matchesRead
  })

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div>
        <div className="flex items-center gap-3">
          {onBack && (
            <Button variant="ghost" size="icon" onClick={onBack}>
              <ArrowLeft className="h-5 w-5" />
            </Button>
          )}
          <div>
            <h1 className="text-3xl font-bold tracking-tight">받은 메일함</h1>
            <p className="text-muted-foreground">받은 메일 목록</p>
          </div>
        </div>
      </div>

      {/* 통계 카드 */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">전체 메일</CardTitle>
            <Inbox className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{emails.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">읽지 않음</CardTitle>
            <Mail className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {emails.filter((e) => !e.read).length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">첨부파일 있음</CardTitle>
            <Paperclip className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {emails.filter((e) => e.attachments && e.attachments.length > 0).length}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 검색 및 필터 */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col gap-4">
            <div className="flex flex-col md:flex-row gap-4">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="제목 또는 보낸 사람으로 검색..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-muted-foreground" />
                <Select value={dateFilter} onValueChange={setDateFilter}>
                  <SelectTrigger className="w-[150px]">
                    <SelectValue placeholder="기간" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">전체 기간</SelectItem>
                    <SelectItem value="today">오늘</SelectItem>
                    <SelectItem value="week">최근 7일</SelectItem>
                    <SelectItem value="month">최근 30일</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={readFilter} onValueChange={setReadFilter}>
                  <SelectTrigger className="w-[150px]">
                    <SelectValue placeholder="읽음" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">전체</SelectItem>
                    <SelectItem value="unread">읽지 않음</SelectItem>
                    <SelectItem value="read">읽음</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 메일 목록 */}
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <p className="text-red-800">{error}</p>
          </CardContent>
        </Card>
      )}

      {loading ? (
        <Card>
          <CardContent className="pt-6">
            <p className="text-center text-muted-foreground">메일을 불러오는 중...</p>
          </CardContent>
        </Card>
      ) : emails.length === 0 ? (
        <Card>
          <CardContent className="pt-6">
            <div className="text-center space-y-4">
              <Inbox className="h-12 w-12 mx-auto text-muted-foreground" />
              <p className="text-muted-foreground">받은 메일이 없습니다</p>
            </div>
          </CardContent>
        </Card>
      ) : filteredEmails.length === 0 ? (
        <Card>
          <CardContent className="pt-6">
            <div className="text-center space-y-4">
              <Search className="h-12 w-12 mx-auto text-muted-foreground" />
              <p className="text-muted-foreground">검색 결과가 없습니다</p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>
              메일 목록 ({filteredEmails.length}개)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[5%]"></TableHead>
                  <TableHead className="w-[40%]">제목</TableHead>
                  <TableHead className="w-[30%]">보낸이</TableHead>
                  <TableHead className="w-[20%]">받은 날짜</TableHead>
                  <TableHead className="w-[5%]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredEmails.map((email) => (
                  <TableRow
                    key={email._id}
                    className={`cursor-pointer ${!email.read ? 'bg-blue-50/30 hover:bg-blue-50/50' : ''}`}
                    onClick={() => onNavigate?.('email-detail', email._id)}
                  >
                    <TableCell>
                      {!email.read && (
                        <div className="h-2 w-2 rounded-full bg-blue-500"></div>
                      )}
                    </TableCell>
                    <TableCell className={`font-medium ${!email.read ? 'font-semibold' : ''}`}>
                      <div className="flex items-center gap-2">
                        <span className="truncate">{email.subject}</span>
                        {email.attachments && email.attachments.length > 0 && (
                          <Paperclip className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className={`text-sm truncate block ${!email.read ? 'font-medium text-foreground' : 'text-muted-foreground'}`}>
                        {email.from_email}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm text-muted-foreground">
                        {formatDate(email.created_at)}
                      </span>
                    </TableCell>
                    <TableCell>
                      {email.attachments && email.attachments.length > 0 && (
                        <Badge variant="secondary" className="text-xs">
                          {email.attachments.length}
                        </Badge>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
