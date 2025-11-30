import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  FileText,
  CheckCircle,
  XCircle,
  Shield,
  Search,
  RefreshCw,
  Clock,
  User,
  Building2,
  AlertTriangle,
  Mail,
  Settings,
  Database,
  Eye,
  ChevronLeft,
  ChevronRight,
  Filter,
  Activity
} from 'lucide-react';

interface AuditLog {
  _id: string;
  timestamp: string;
  event_type: string;
  severity: string;
  user_email: string;
  user_role: string;
  action: string;
  resource_type?: string;
  resource_id?: string;
  details: Record<string, any>;
  ip_address?: string;
  success: boolean;
  error_message?: string;
}

export default function AuditorDashboardPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [totalPages, setTotalPages] = useState(0);
  const [searchTerm, setSearchTerm] = useState('');
  const [eventTypeFilter, setEventTypeFilter] = useState<string>('');
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);

  useEffect(() => {
    loadLogs();
  }, [page, eventTypeFilter, severityFilter]);

  const loadLogs = async () => {
    const token = localStorage.getItem('auth_token');
    if (!token) {
      console.error('❌ 인증 토큰이 없습니다.');
      return;
    }

    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: pageSize.toString(),
      });

      if (eventTypeFilter) params.append('event_type', eventTypeFilter);
      if (severityFilter) params.append('severity', severityFilter);
      if (searchTerm) params.append('search', searchTerm);

      console.log('📤 감사 로그 요청:', `http://localhost:8000/api/audit/logs?${params}`);

      const response = await fetch(`http://localhost:8000/api/audit/logs?${params}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      console.log('📥 감사 로그 응답:', response.status);

      if (response.ok) {
        const result = await response.json();
        console.log('✅ 감사 로그 데이터:', result);
        setLogs(result.data.logs);
        setTotal(result.data.total);
        setTotalPages(result.data.total_pages);
      } else {
        const errorData = await response.json().catch(() => ({}));
        console.error('❌ 감사 로그 로드 실패:', response.status, errorData);
      }
    } catch (error) {
      console.error('❌ 감사 로그 로드 중 오류:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    setPage(1);
    loadLogs();
  };

  const getEventIcon = (eventType: string) => {
    if (eventType.includes('email')) return <Mail className="w-4 h-4" />;
    if (eventType.includes('masking')) return <Shield className="w-4 h-4" />;
    if (eventType.includes('entity')) return <Database className="w-4 h-4" />;
    // ✅ 엔티티/정책 아이콘
    if (eventType.includes('policy')) return <FileText className="w-4 h-4" />;
    if (eventType.includes('settings') || eventType.includes('env')) return <Settings className="w-4 h-4" />;
    if (eventType.includes('vector_store') || eventType.includes('policy')) return <FileText className="w-4 h-4" />;
    if (eventType.includes('login') || eventType.includes('auth')) return <User className="w-4 h-4" />;
    return <Eye className="w-4 h-4" />;
  };

  const getSeverityBadge = (severity: string) => {
    const variants: Record<string, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
      info: { label: '정보', variant: 'default' },
      warning: { label: '경고', variant: 'secondary' },
      error: { label: '오류', variant: 'destructive' },
      critical: { label: '심각', variant: 'destructive' },
    };
    const config = variants[severity] || variants.info;
    return <Badge variant={config.variant} className="text-xs">{config.label}</Badge>;
  };

  const formatEventType = (type: string) => {
    const labels: Record<string, string> = {
      'email_send': '이메일 전송',
      'email_read': '이메일 읽음',
      'email_compose': '이메일 작성',
      'masking_decision': '마스킹 결정',
      'masking_apply': '마스킹 적용',
      'entity_create': '엔티티 생성',
      'entity_update': '엔티티 수정',
      'entity_delete': '엔티티 삭제',
      // ✅ 정책 관련 (추가)
      'policy_upload': '정책 업로드',
      'policy_update': '정책 수정',
      'policy_delete': '정책 삭제',

      'settings_update': '설정 변경',
      'env_change': '환경변수 변경',
      'vector_store_sync': 'Vector Store 동기화',
      'login': '로그인',
      'logout': '로그아웃',
      'auth_fail': '인증 실패',
    };
    return labels[type] || type;
  };

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">감사 로그</h1>
          <p className="text-muted-foreground">시스템의 모든 활동을 추적하고 감사합니다</p>
        </div>
        <Button onClick={loadLogs} disabled={loading}>
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          새로고침
        </Button>
      </div>

      {/* Statistics */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">총 로그</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{total}</div>
            <p className="text-xs text-muted-foreground">전체 감사 기록</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">성공</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {logs.filter(l => l.success).length}
            </div>
            <p className="text-xs text-muted-foreground">정상 처리됨</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">실패</CardTitle>
            <XCircle className="h-4 w-4 text-red-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {logs.filter(l => !l.success).length}
            </div>
            <p className="text-xs text-muted-foreground">오류 발생</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">경고</CardTitle>
            <AlertTriangle className="h-4 w-4 text-amber-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600">
              {logs.filter(l => l.severity === 'warning' || l.severity === 'error').length}
            </div>
            <p className="text-xs text-muted-foreground">주의 필요</p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Filter className="w-5 h-5" />
            필터 및 검색
          </CardTitle>
          <CardDescription>로그를 검색하고 필터링합니다</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap gap-4">
              <div className="flex-1 min-w-[250px]">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-4 h-4" />
                  <Input
                    placeholder="사용자, 액션, 리소스 ID 검색..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                    className="pl-9"
                  />
                </div>
              </div>

              <Select value={eventTypeFilter || undefined} onValueChange={(val) => setEventTypeFilter(val === 'all' ? '' : val)}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="이벤트 타입" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">전체</SelectItem>
                  <SelectItem value="email_send">이메일 전송</SelectItem>
                  <SelectItem value="masking_decision">마스킹 결정</SelectItem>
                  <SelectItem value="entity_create">엔티티 생성</SelectItem>
                  <SelectItem value="entity_update">엔티티 수정</SelectItem>
                  <SelectItem value="entity_delete">엔티티 삭제</SelectItem>
                  <SelectItem value="policy_upload">정책 업로드</SelectItem>
                  <SelectItem value="policy_update">정책 수정</SelectItem>
                  <SelectItem value="policy_delete">정책 삭제</SelectItem>
                  <SelectItem value="settings_update">설정 변경</SelectItem>
                  <SelectItem value="vector_store_sync">Vector Store 동기화</SelectItem>
                </SelectContent>
              </Select>


              <Button onClick={handleSearch} variant="secondary">
                <Search className="w-4 h-4 mr-2" />
                검색
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Logs Table */}
      <Card>
        <CardHeader>
          <CardTitle>감사 로그 ({total}건)</CardTitle>
          <CardDescription>최근 활동 내역</CardDescription>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[600px]">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[180px]">시간</TableHead>
                  <TableHead>이벤트</TableHead>
                  <TableHead>사용자</TableHead>
                  <TableHead>액션</TableHead>
                  <TableHead className="w-[80px]">상태</TableHead>
                  <TableHead className="w-[100px]">상세</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.map((log) => (
                  <TableRow
                    key={log._id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => setSelectedLog(log)}
                  >
                    <TableCell className="font-mono text-xs">
                      <div className="flex items-center gap-2">
                        <Clock className="w-3 h-3 text-muted-foreground" />
                        {new Date(log.timestamp).toLocaleString('ko-KR', {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {getEventIcon(log.event_type)}
                        <span className="text-sm">{formatEventType(log.event_type)}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="text-sm font-medium">{log.user_email}</span>
                        <span className="text-xs text-muted-foreground">{log.user_role}</span>
                      </div>
                    </TableCell>
                    <TableCell className="max-w-[300px] truncate">
                      <span className="text-sm">{log.action}</span>
                    </TableCell>
                    <TableCell>
                      {log.success ? (
                        <Badge variant="outline" className="text-green-600 border-green-600">
                          성공
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-red-600 border-red-600">
                          실패
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <Button variant="ghost" size="sm">
                        상세보기
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            {!loading && logs.length === 0 && (
              <div className="flex flex-col items-center justify-center py-12">
                <FileText className="w-12 h-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-semibold mb-1">로그가 없습니다</h3>
                <p className="text-sm text-muted-foreground">필터를 변경하거나 다시 시도해보세요</p>
              </div>
            )}
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            <ChevronLeft className="w-4 h-4" />
          </Button>

          <div className="text-sm text-muted-foreground">
            페이지 {page} / {totalPages}
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      )}

      {/* Detail Modal */}
      {selectedLog && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedLog(null)}
        >
          <Card
            className="max-w-2xl w-full max-h-[80vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {getEventIcon(selectedLog.event_type)}
                로그 상세 정보
              </CardTitle>
              <CardDescription>{selectedLog.action}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">타임스탬프</p>
                  <p className="text-sm">{new Date(selectedLog.timestamp).toLocaleString('ko-KR')}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">이벤트 타입</p>
                  <p className="text-sm">{formatEventType(selectedLog.event_type)}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">사용자</p>
                  <p className="text-sm">{selectedLog.user_email}</p>
                  <p className="text-xs text-muted-foreground">{selectedLog.user_role}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">심각도</p>
                  {getSeverityBadge(selectedLog.severity)}
                </div>
                {selectedLog.resource_type && (
                  <>
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">리소스 타입</p>
                      <p className="text-sm">{selectedLog.resource_type}</p>
                    </div>
                    {selectedLog.resource_id && (
                      <div>
                        <p className="text-sm font-medium text-muted-foreground">리소스 ID</p>
                        <p className="text-sm font-mono">{selectedLog.resource_id}</p>
                      </div>
                    )}
                  </>
                )}
                {selectedLog.ip_address && (
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">IP 주소</p>
                    <p className="text-sm font-mono">{selectedLog.ip_address}</p>
                  </div>
                )}
              </div>

              <Separator />

              {Object.keys(selectedLog.details).length > 0 && (
                <div>
                  <p className="text-sm font-medium mb-2">상세 정보</p>
                  <pre className="text-xs bg-muted p-4 rounded-md overflow-auto">
                    {JSON.stringify(selectedLog.details, null, 2)}
                  </pre>
                </div>
              )}

              {!selectedLog.success && selectedLog.error_message && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <p className="text-sm font-medium text-red-800 mb-1">오류 메시지</p>
                  <p className="text-sm text-red-600">{selectedLog.error_message}</p>
                </div>
              )}

              <div className="flex justify-end">
                <Button onClick={() => setSelectedLog(null)}>닫기</Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
