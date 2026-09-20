import { describe, expect, it } from 'vitest'
import { isSensitiveConfigKey, SENSITIVE_CONFIG_VALUE } from '../system'

describe('system config secret display contract', () => {
  it('recognizes credential-bearing keys', () => {
    expect(isSensitiveConfigKey('cloud.aliyun.secret_key')).toBe(true)
    expect(isSensitiveConfigKey('storage.s3.access_key_id')).toBe(true)
    expect(isSensitiveConfigKey('notification.dingtalk_webhook')).toBe(true)
    expect(isSensitiveConfigKey('integration.api_key')).toBe(true)
    expect(isSensitiveConfigKey('runner.credential')).toBe(true)
    expect(isSensitiveConfigKey('agent.offline_threshold_seconds')).toBe(false)
  })

  it('uses a fixed mask instead of exposing the stored value', () => {
    expect(SENSITIVE_CONFIG_VALUE).toBe('********')
  })
})
