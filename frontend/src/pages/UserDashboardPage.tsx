import { useState, useEffect } from 'react'
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
import { Mail, Paperclip, ArrowLeft, Search, Filter, Inbox, Send } from 'lucide-react'

interface Email {
  _id: string
  subject: string
  to_email?: string
  from_email?: string
  created_at: string
  sent_at?: string
  attachments?: any[]
  type: 'sent' | 'received'
  status?: 'sent' | 'failed' | 'received'
  read?: boolean
}

interface UserDashboardPageProps {
  onNavigate?: (view: string, emailId?: string) => void
}

export function UserDashboardPage({ onNavigate }: UserDashboardPageProps) {
  const [emails, setEmails] = useState<Email[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState<string>('all')

  useEffect(() => {
    loadEmails()
  }, [])

  const loadEmails = async () => {
    try {
      setLoading(true)
      const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
      const token = localStorage.getItem('auth_token')

      if (!token) {
        throw new Error('인증 토큰이 없습니다.')
      }

      // 사용자 정보 가져오기
      const userJson = localStorage.getItem('user')
      if (!userJson) {
        throw new Error('사용자 정보가 없습니다.')
      }
      const user = JSON.parse(userJson)

      // 보낸 메일과 받은 메일을 병렬로 가져오기
      const [sentResponse, receivedResponse] = await Promise.all([
        fetch(`${API_BASE}/api/v1/files/original_emails?from_email=${encodeURIComponent(user.email)}&limit=100`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch(`${API_BASE}/api/v1/emails/received-emails`, {
          headers: { Authorization: `Bearer ${token}` },
        })
      ])

      const allEmails: Email[] = []

      // 보낸 메일 처리
      if (sentResponse.ok) {
        const sentResult = await sentResponse.json()
        if (sentResult.success && sentResult.data) {
          const sentEmails = sentResult.data.map((email: any) => ({
            ...email,
            _id: email.email_id,
            to_email: email.to_emails?.[0] || '',
            created_at: email.created_at,
            attachments: email.attachments_summary || [],
            type: 'sent' as const,
            status: (email.status === 'failed' ? 'failed' : 'sent') as 'sent' | 'failed'
          }))
          allEmails.push(...sentEmails)
        }
      }

      // 받은 메일 처리
      if (receivedResponse.ok) {
        const receivedData = await receivedResponse.json()
        const receivedEmails = receivedData.map((email: any) => ({
          ...email,
          type: 'received' as const,
          status: 'received' as const
        }))
        allEmails.push(...receivedEmails)
      }

      // 날짜순으로 정렬 (최신순)
      allEmails.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())

      setEmails(allEmails)
      setError(null)
    } catch (err) {
      console.error('Error loading emails:', err)
      setError(err instanceof Error ? err.message : '오류가 발생했습니다.')
    } finally {
      setLoading(false)
    }
  }

  // ✅ 이메일 클릭 핸들러 - 보낸 메일은 sent-email-detail로 이동
  const handleEmailClick = (email: Email) => {
    if (email.type === 'sent') {
      onNavigate?.('sent-email-detail', email._id)
    } else {
      onNavigate?.('email-detail', email._id)
    }
  }

  const getTypeBadge = (email: Email) => {
    const status = email.status || (email.type === 'sent' ? 'sent' : 'received')

    if (status === 'sent') {
      return (
        <Badge variant="default" className="gap-1">
          <Send className="h-3 w-3" />
          <span>전송</span>
        </Badge>
      )
    } else if (status === 'failed') {
      return (
        <Badge variant="destructive" className="gap-1">
          <Send className="h-3 w-3" />
          <span>전송 실패</span>
        </Badge>
      )
    } else {
      return (
        <Badge variant="secondary" className="gap-1">
          <Inbox className="h-3 w-3" />
          <span>수신</span>
        </Badge>
      )
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

  // 필터링된 메일 목록
  const filteredEmails = emails.filter((email) => {
    const matchesSearch =
      email.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
      email.to_email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      email.from_email?.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesType = typeFilter === 'all' || email.type === typeFilter
    return matchesSearch && matchesType
  })

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">메일함</h1>
        <p className="text-muted-foreground">받은 메일과 보낸 메일 목록</p>
      </div>

      {/* 통계 카드 */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">전체 메일</CardTitle>
            <Mail className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{emails.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">보낸 메일</CardTitle>
            <Send className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {emails.filter((e) => e.type === 'sent').length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">받은 메일</CardTitle>
            <Inbox className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {emails.filter((e) => e.type === 'received').length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">읽지 않음</CardTitle>
            <Mail className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {emails.filter((e) => e.type === 'received' && !e.read).length}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 검색 및 필터 */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="제목, 받는 사람, 보낸 사람으로 검색..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <Select value={typeFilter} onValueChange={setTypeFilter}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="메일 유형" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">전체</SelectItem>
                  <SelectItem value="sent">보낸 메일</SelectItem>
                  <SelectItem value="received">받은 메일</SelectItem>
                </SelectContent>
              </Select>
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
              <Mail className="h-12 w-12 mx-auto text-muted-foreground" />
              <p className="text-muted-foreground">메일이 없습니다</p>
              <Button onClick={() => onNavigate?.('write-email')}>
                <Mail className="h-4 w-4 mr-2" />
                메일 작성하기
              </Button>
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
                  <TableHead className="w-[30%]">제목</TableHead>
                  <TableHead className="w-[18%]">보낸이</TableHead>
                  <TableHead className="w-[18%]">받는이</TableHead>
                  <TableHead className="w-[12%]">유형</TableHead>
                  <TableHead className="w-[12%]">날짜</TableHead>
                  <TableHead className="w-[5%]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredEmails.map((email) => (
                  <TableRow
                    key={email._id}
                    className={`cursor-pointer ${
                      email.type === 'received' && !email.read ? 'bg-blue-50/30 hover:bg-blue-50/50' : ''
                    }`}
                    onClick={() => handleEmailClick(email)}
                  >
                    <TableCell>
                      {email.type === 'received' && !email.read && (
                        <div className="h-2 w-2 rounded-full bg-blue-500"></div>
                      )}
                    </TableCell>
                    <TableCell className={`font-medium ${
                      email.type === 'received' && !email.read ? 'font-semibold' : ''
                    }`}>
                      <div className="flex items-center gap-2">
                        <span className="truncate">{email.subject}</span>
                        {email.attachments && email.attachments.length > 0 && (
                          <Paperclip className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className={`text-sm truncate block ${
                        email.type === 'received' && !email.read
                          ? 'font-medium text-foreground'
                          : 'text-muted-foreground'
                      }`}>
                        {email.from_email || '-'}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className={`text-sm truncate block ${
                        email.type === 'received' && !email.read
                          ? 'font-medium text-foreground'
                          : 'text-muted-foreground'
                      }`}>
                        {email.to_email || '-'}
                      </span>
                    </TableCell>
                    <TableCell>{getTypeBadge(email)}</TableCell>
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