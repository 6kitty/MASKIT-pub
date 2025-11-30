import * as React from 'react'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { LogOut } from 'lucide-react'

interface ModernAppLayoutProps {
  children: React.ReactNode
  userName?: string
  userEmail?: string
  userRole?: string
  onLogout?: () => void
  sidebarMenu: Array<{
    id: string
    label: string
    icon: React.ReactNode
    onClick: () => void
  }>
}

export function ModernAppLayout({
  children,
  userName = 'User',
  userEmail = 'user@example.com',
  userRole = 'user',
  onLogout,
  sidebarMenu,
}: ModernAppLayoutProps) {
  // 메뉴를 카테고리별로 그룹화
  const emailMenuItems = sidebarMenu.filter((item) =>
    ['write-email', 'received-emails', 'my-emails'].includes(item.id)
  )
  const policyMenuItems = sidebarMenu.filter((item) =>
    ['policy-dashboard', 'policy-list', 'policy-add', 'entity-management'].includes(item.id)
  )
  const systemMenuItems = sidebarMenu.filter((item) =>
    ['users', 'logs', 'mypage', 'settings'].includes(item.id)
  )
  const mainMenuItems = sidebarMenu.filter((item) => item.id === 'main')

  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full">
        <Sidebar>
          <SidebarHeader>
            <div className="flex items-center gap-2 px-4 py-2">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg overflow-hidden">
                <img src="/logo.png" alt="Logo" className="h-12 w-12 object-contain" />
              </div>
              <div className="flex flex-col mt-1.5">
                <span className="text-sm font-semibold">MASKIT</span>
                <span className="text-xs text-muted-foreground">PBL: 헨젤과 그레텔</span>
              </div>
            </div>
          </SidebarHeader>

          <SidebarContent>
            {/* 메인 */}
            {mainMenuItems.length > 0 && (
              <SidebarGroup>
                <SidebarGroupContent>
                  <SidebarMenu>
                    {mainMenuItems.map((item) => (
                      <SidebarMenuItem key={item.id}>
                        <SidebarMenuButton onClick={item.onClick}>
                          {item.icon}
                          <span>{item.label}</span>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    ))}
                  </SidebarMenu>
                </SidebarGroupContent>
              </SidebarGroup>
            )}

            {/* 이메일 */}
            {emailMenuItems.length > 0 && (
              <SidebarGroup>
                <SidebarGroupLabel>이메일</SidebarGroupLabel>
                <SidebarGroupContent>
                  <SidebarMenu>
                    {emailMenuItems.map((item) => (
                      <SidebarMenuItem key={item.id}>
                        <SidebarMenuButton onClick={item.onClick}>
                          {item.icon}
                          <span>{item.label}</span>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    ))}
                  </SidebarMenu>
                </SidebarGroupContent>
              </SidebarGroup>
            )}

            {/* 정책 관리 */}
            {policyMenuItems.length > 0 && (
              <SidebarGroup>
                <SidebarGroupLabel>정책 관리</SidebarGroupLabel>
                <SidebarGroupContent>
                  <SidebarMenu>
                    {policyMenuItems.map((item) => (
                      <SidebarMenuItem key={item.id}>
                        <SidebarMenuButton onClick={item.onClick}>
                          {item.icon}
                          <span>{item.label}</span>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    ))}
                  </SidebarMenu>
                </SidebarGroupContent>
              </SidebarGroup>
            )}

            {/* 시스템 */}
            {systemMenuItems.length > 0 && (
              <SidebarGroup>
                <SidebarGroupLabel>시스템</SidebarGroupLabel>
                <SidebarGroupContent>
                  <SidebarMenu>
                    {systemMenuItems.map((item) => (
                      <SidebarMenuItem key={item.id}>
                        <SidebarMenuButton onClick={item.onClick}>
                          {item.icon}
                          <span>{item.label}</span>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    ))}
                  </SidebarMenu>
                </SidebarGroupContent>
              </SidebarGroup>
            )}
          </SidebarContent>

          <SidebarFooter>
            <SidebarMenu>
              <SidebarMenuItem>
                <div className="flex items-center gap-3 px-3 py-2">
                  <Avatar className="h-8 w-8">
                    <AvatarFallback className="bg-primary text-primary-foreground">
                      {userName?.charAt(0) || 'U'}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex flex-1 flex-col text-left text-sm">
                    <span className="truncate font-semibold">{userName}</span>
                    <span className="truncate text-xs text-muted-foreground">{userEmail}</span>
                  </div>
                  <Button variant="ghost" size="icon" onClick={onLogout} title="로그아웃">
                    <LogOut className="h-4 w-4" />
                  </Button>
                </div>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarFooter>
        </Sidebar>

        <main className="flex flex-1 flex-col">
          <header className="sticky top-0 z-10 flex h-14 items-center gap-4 border-b bg-background px-4 sm:px-6">
            <SidebarTrigger />
            <div className="flex flex-1 items-center justify-between">


            </div>
          </header>
          <div className="flex-1 overflow-auto p-4 sm:p-6">{children}</div>
        </main>
      </div>
    </SidebarProvider>
  )
}
