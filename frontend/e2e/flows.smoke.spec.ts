import { expect, test, type Page } from '@playwright/test'

async function signIn(page: Page) {
  await page.goto('/login?redirect=/flows')
  await page.getByPlaceholder('请输入用户名').fill('demo-admin')
  await page.getByPlaceholder('请输入密码').fill('testing')
  await page.getByRole('button', { name: '登录' }).click()
  await expect.poll(() => page.evaluate(() => location.pathname)).toBe('/flows')
}

async function expectNoHorizontalOverflow(page: Page) {
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth))
    .toBe(true)
}

test.beforeEach(async ({ page }) => {
  await signIn(page)
})

test('flow list stays compact and opens a start form with global variables only', async ({ page }) => {
  await expect(page.getByRole('button', { name: '新建流程' })).toBeVisible()
  await expect(page.getByRole('tab', { name: '执行记录' })).toHaveCount(0)
  await expectNoHorizontalOverflow(page)

  await page.getByRole('button', { name: '启动' }).first().click()
  const dialog = page.locator('.arco-modal:visible')
  await expect(dialog).toContainText('全局变量')
  await expect(dialog).not.toContainText(/Agent Server|调度 Agent/i)
  await expect(dialog).not.toContainText('节点参数覆盖')
  await expect(dialog.locator('[data-testid="host-selector"]')).toHaveCount(0)
  await expectNoHorizontalOverflow(page)
})

test('new global-variable rows survive typing and host lists use text input', async ({ page }) => {
  await page.goto('/flows/create')
  await page.getByRole('button', { name: '全局变量' }).click()
  await page.getByRole('button', { name: '新增变量' }).click()

  const key = page.getByPlaceholder('Key，例如 CheckHost')
  await expect(key).toBeVisible()
  await key.fill('CheckHost')
  await expect(key).toHaveValue('CheckHost')

  const name = page.getByPlaceholder('显示名称，例如 执行脚本机器')
  await name.fill('执行脚本机器')
  await expect(name).toHaveValue('执行脚本机器')
  await expect(page.getByText('引用：${CheckHost}')).toBeVisible()

  await page.getByTitle('文本').click()
  await page.getByRole('listitem').filter({ hasText: '主机列表' }).click()
  await expect(page.getByPlaceholder('每行一个 IP 或主机名（可选）')).toBeVisible()
  await expect(page.getByText(/主机\s*ID/i)).toHaveCount(0)
  await expect(page.locator('[data-testid="host-selector"]')).toHaveCount(0)
  await expectNoHorizontalOverflow(page)
})

test('multiple blank global-variable rows survive type changes independently', async ({ page }) => {
  await page.goto('/flows/create')
  await page.getByRole('button', { name: '全局变量' }).click()

  const addVariable = page.getByRole('button', { name: '新增变量' })
  await addVariable.click()
  await addVariable.click()
  await addVariable.click()
  await addVariable.click()

  const rows = page.locator('.variable-row')
  await expect(rows).toHaveCount(4)

  await rows.nth(0).getByTitle('文本').click()
  await page.locator('.arco-select-dropdown:visible').last().getByText('密文', { exact: true }).click()
  await expect(rows).toHaveCount(4)
  await expect(rows.nth(0).getByTitle('密文')).toBeVisible()

  await rows.nth(1).getByTitle('文本').click()
  await page.locator('.arco-select-dropdown:visible').last().getByText('数字', { exact: true }).click()

  await expect(rows).toHaveCount(4)
  await expect(rows.nth(1).getByTitle('数字')).toBeVisible()

  await rows.nth(2).getByTitle('文本').click()
  await page.locator('.arco-select-dropdown:visible').last().getByText('布尔', { exact: true }).click()

  await expect(rows).toHaveCount(4)
  await expect(rows.nth(2).getByTitle('布尔')).toBeVisible()

  await rows.nth(3).getByTitle('文本').click()
  await page.locator('.arco-select-dropdown:visible').last().getByText('主机列表', { exact: true }).click()

  await expect(rows).toHaveCount(4)
  await expect(rows.nth(0).getByTitle('密文')).toBeVisible()
  await expect(rows.nth(1).getByTitle('数字')).toBeVisible()
  await expect(rows.nth(2).getByTitle('布尔')).toBeVisible()
  await expect(rows.nth(3).getByTitle('主机列表')).toBeVisible()
})

test('deleting one global-variable draft preserves the other drafts', async ({ page }) => {
  await page.goto('/flows/create')
  await page.getByRole('button', { name: '全局变量' }).click()

  const addVariable = page.getByRole('button', { name: '新增变量' })
  await addVariable.click()
  await addVariable.click()
  await addVariable.click()
  await addVariable.click()

  const rows = page.locator('.variable-row')
  const keys = page.getByPlaceholder('Key，例如 CheckHost')
  await expect(rows).toHaveCount(4)
  await keys.nth(0).fill('FirstHost')
  await keys.nth(3).fill('LastHost')
  await expect(rows).toHaveCount(4)

  await rows.nth(1).locator('button').click()

  await expect(rows).toHaveCount(3)
  await expect(keys.nth(0)).toHaveValue('FirstHost')
  await expect(keys.nth(1)).toHaveValue('')
  await expect(keys.nth(2)).toHaveValue('LastHost')
  await expect(page.getByText('引用：${FirstHost}')).toBeVisible()
  await expect(page.getByText('引用：${LastHost}')).toBeVisible()
})

test('edit and readonly workbenches render the same persisted topology without overflow', async ({ page }) => {
  await page.goto('/flows/801/edit')
  await expect(page.locator('.vue-flow__node')).toHaveCount(3)
  await expect(page.locator('.vue-flow__edge')).toHaveCount(2)
  await page.locator('.vue-flow__node').first().click()
  await expect(page.locator('.arco-drawer:visible')).toHaveCount(1)
  await expectNoHorizontalOverflow(page)

  await page.goto('/flows/801/detail')
  await expect(page.locator('.vue-flow__node')).toHaveCount(3)
  await expect(page.locator('.vue-flow__edge')).toHaveCount(2)
  await page.locator('.vue-flow__node').first().click()
  await expect(page.locator('.arco-drawer:visible')).toHaveCount(1)
  await expect(page.getByRole('button', { name: '保存' })).toHaveCount(0)
  await expectNoHorizontalOverflow(page)
})

test('run detail hides control-plane and raw host identifiers', async ({ page }) => {
  await page.goto('/flows/runs/8801')
  await expect(page.getByText(/执行中|成功|失败|已暂停|已取消/).first()).toBeVisible()
  await expect(page.locator('body')).not.toContainText(/主机\s*ID|host_id/i)
  await expect(page.locator('body')).not.toContainText(/Agent Server|调度 Agent/i)
  await expectNoHorizontalOverflow(page)
})