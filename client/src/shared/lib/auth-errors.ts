type AuthenticationError = { status?: number } | null | undefined

export function getAuthErrorMessage(error: AuthenticationError): string {
  if (error?.status === 401) {
    return 'Email hoặc mật khẩu không chính xác. Vui lòng kiểm tra và thử lại.'
  }

  return 'Không thể đăng nhập lúc này. Vui lòng thử lại sau.'
}
