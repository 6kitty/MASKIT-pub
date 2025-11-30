import React, { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from 'sonner'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

interface LoginFormData {
  userId: string
  userName: string
  userEmail: string
  userTeam: string
  userRole: string
}

interface LoginPageProps {
  onLogin?: (data: LoginFormData) => void
  onShowRegister?: () => void
}

export const LoginPage: React.FC<LoginPageProps> = ({
  onLogin,
  onShowRegister,
}) => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!email || !password) {
      toast.error('이메일과 비밀번호를 입력해주세요')
      return
    }

    setIsLoading(true)

    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          password,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || '로그인에 실패했습니다')
      }

      const data = await response.json()

      // 토큰 저장
      localStorage.setItem('auth_token', data.access_token)
      localStorage.setItem('user', JSON.stringify(data.user))

      toast.success('로그인 성공!')

      // 사용자 정보 전달
      const userData: LoginFormData = {
        userId: data.user.email,
        userName: data.user.nickname || data.user.email,
        userEmail: data.user.email,
        userTeam: data.user.team_name || '',
        userRole: data.user.role || 'user',
      }

      onLogin?.(userData)
    } catch (error) {
      console.error('로그인 오류:', error)
      toast.error(error instanceof Error ? error.message : '로그인에 실패했습니다')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-primary/10 via-background to-primary/5 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-2 text-center">
          <div className="flex justify-center mb-0">
            <img 
              src="/logo.png" 
              alt="MASKIT Logo" 
              className="h-20 w-20 object-contain"
            />
          </div>
          <CardTitle className="text-3xl font-bold text-primary">MASKIT</CardTitle>
          <CardDescription className="text-base">이메일 마스킹 agent</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">이메일</Label>
              <Input
                id="email"
                type="email"
                placeholder="이메일 주소"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={isLoading}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">비밀번호</Label>
              <Input
                id="password"
                type="password"
                placeholder="비밀번호"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={isLoading}
              />
            </div>

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? '로그인 중...' : '로그인'}
            </Button>
          </form>


          <div className="mt-6 text-center text-sm">
            <span className="text-muted-foreground">
              아직 계정이 없으신가요?{' '}
            </span>
            <button
              type="button"
              onClick={onShowRegister}
              className="font-semibold text-primary hover:underline"
            >
              회원가입
            </button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
