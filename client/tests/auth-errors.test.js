import assert from 'node:assert/strict'
import { test } from 'node:test'
import { getAuthErrorMessage } from '../src/shared/lib/auth-errors.js'

test('getAuthErrorMessage translates invalid credentials into the approved Vietnamese login error', () => {
  assert.equal(
    getAuthErrorMessage({ status: 401 }),
    'Email hoặc mật khẩu không chính xác. Vui lòng kiểm tra và thử lại.',
  )
})

test('getAuthErrorMessage keeps unexpected authentication failures understandable in Vietnamese', () => {
  assert.equal(
    getAuthErrorMessage({ status: 500 }),
    'Không thể đăng nhập lúc này. Vui lòng thử lại sau.',
  )
})
