<template>
  <header class="travel-nav">
    <nav class="nav-inner" :aria-label="t('app.brand')">
      <button class="brand" type="button" @click="handleBrandClick">
        <img src="/travel-mark.svg" alt="" width="34" height="34" />
        <span>{{ t('app.brand') }}</span>
      </button>
      <div class="nav-actions">
        <a-select v-model:value="locale" class="lang-select-nav" :aria-label="t('app.language.label')">
          <a-select-option value="zh-CN">{{ t('app.language.zh') }}</a-select-option>
          <a-select-option value="ja-JP">{{ t('app.language.ja') }}</a-select-option>
          <a-select-option value="en-US">{{ t('app.language.en') }}</a-select-option>
        </a-select>
        <button type="button" class="settings-btn" :title="t('settings.open')" :aria-label="t('settings.open')" @click="openSettingsDialog">
          <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3" fill="white"/><circle cx="15" cy="17" r="3" fill="white"/></svg>
          <span>{{ t('settings.title') }}</span>
        </button>
        <button type="button" class="nav-cta" @click="handleCtaClick">{{ t('home.nav.cta') }} <span aria-hidden="true">↗</span></button>
      </div>
    </nav>
    <a-modal
      v-model:open="settingsVisible"
      class="settings-modal"
      :title="t('settings.title')"
      :width="820"
      :confirm-loading="settingsSaving"
      :ok-text="t('settings.saveApply')"
      :cancel-text="t('settings.cancel')"
      @ok="saveSettingsNow"
    >
      <a-spin :spinning="settingsLoading">
        <section class="runtime-settings-panel">

          <a-form layout="vertical" class="runtime-settings-form">
            <div class="runtime-settings-grid">
              <a-form-item>
                <template #label>
                  <span class="field-label">{{ t('settings.labels.apiBaseUrl') }}</span>
                </template>
                <a-input
                  v-model:value="settingsForm.api_base_url"
                  :placeholder="t('settings.placeholders.apiBaseUrl')"
                  allow-clear
                />
              </a-form-item>

              <a-form-item>
                <template #label>
                  <span class="field-label">{{ t('settings.labels.amapJsKey') }}</span>
                </template>
                <a-input-password v-model:value="settingsForm.vite_amap_web_js_key" allow-clear />
              </a-form-item>

              <a-form-item>
                <template #label>
                  <span class="field-label">{{ t('settings.labels.amapWebKey') }}</span>
                </template>
                <a-input-password v-model:value="settingsForm.vite_amap_web_key" allow-clear />
              </a-form-item>

              <a-form-item>
                <template #label>
                  <span class="field-label">{{ t('settings.labels.googleMapsApiKey') }}</span>
                </template>
                <a-input-password
                  v-model:value="settingsForm.google_maps_api_key"
                  :placeholder="t('settings.placeholders.googleMapsApiKey')"
                  allow-clear
                />
              </a-form-item>

              <a-form-item>
                <template #label>
                  <span class="field-label">{{ t('settings.labels.googleMapsProxy') }}</span>
                </template>
                <a-input
                  v-model:value="settingsForm.google_maps_proxy"
                  :placeholder="t('settings.placeholders.googleMapsProxy')"
                  allow-clear
                />
              </a-form-item>

              <a-form-item>
                <template #label>
                  <span class="field-label">{{ t('settings.labels.openaiBaseUrl') }}</span>
                </template>
                <a-input
                  v-model:value="settingsForm.openai_base_url"
                  :placeholder="t('settings.placeholders.openaiBaseUrl')"
                  allow-clear
                />
              </a-form-item>

              <a-form-item>
                <template #label>
                  <span class="field-label">{{ t('settings.labels.openaiModel') }}</span>
                </template>
                <a-input
                  v-model:value="settingsForm.openai_model"
                  :placeholder="t('settings.placeholders.openaiModel')"
                  allow-clear
                />
              </a-form-item>

              <a-form-item>
                <template #label>
                  <span class="field-label">{{ t('settings.labels.openaiApiKey') }}</span>
                </template>
                <a-input-password v-model:value="settingsForm.openai_api_key" allow-clear />
              </a-form-item>
            </div>

            <a-form-item class="runtime-settings-full">
              <template #label>
                <span class="field-label">{{ t('settings.labels.xhsCookie') }}</span>
              </template>
              <a-textarea
                v-model:value="settingsForm.xhs_cookie"
                :rows="4"
                :placeholder="t('settings.placeholders.xhsCookie')"
                allow-clear
              />
            </a-form-item>
          </a-form>
        </section>
      </a-spin>
    </a-modal>
  </header>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import type { RuntimeSettings } from '@/types'
import { getRuntimeSettings, saveRuntimeSettings } from '@/services/api'

const { t, locale } = useI18n()
const settingsVisible = ref(false)
const settingsLoading = ref(false)
const settingsSaving = ref(false)
const settingsForm = reactive<RuntimeSettings>({
  api_base_url: '',
  vite_amap_web_key: '',
  vite_amap_web_js_key: '',
  google_maps_api_key: '',
  google_maps_proxy: '',
  xhs_cookie: '',
  openai_api_key: '',
  openai_base_url: '',
  openai_model: '',
})

const emit = defineEmits<{
  (e: 'brand-click'): void
  (e: 'cta-click'): void
}>()

const handleBrandClick = () => {
  emit('brand-click')
}

const handleCtaClick = () => {
  emit('cta-click')
}

const applyRuntimeSettings = (settings: RuntimeSettings) => {
  settingsForm.api_base_url = settings.api_base_url || ''
  settingsForm.vite_amap_web_key = settings.vite_amap_web_key || ''
  settingsForm.vite_amap_web_js_key = settings.vite_amap_web_js_key || ''
  settingsForm.google_maps_api_key = settings.google_maps_api_key || ''
  settingsForm.google_maps_proxy = settings.google_maps_proxy || ''
  settingsForm.xhs_cookie = settings.xhs_cookie || ''
  settingsForm.openai_api_key = settings.openai_api_key || ''
  settingsForm.openai_base_url = settings.openai_base_url || ''
  settingsForm.openai_model = settings.openai_model || ''
}

const openSettingsDialog = async () => {
  settingsVisible.value = true
  settingsLoading.value = true
  try {
    const settings = await getRuntimeSettings()
    applyRuntimeSettings(settings)
  } catch (error: any) {
    message.error(error?.message || t('settings.messages.loadFailed'))
  } finally {
    settingsLoading.value = false
  }
}

const saveSettingsNow = async () => {
  settingsSaving.value = true
  try {
    const payload: RuntimeSettings = {
      api_base_url: settingsForm.api_base_url,
      vite_amap_web_key: settingsForm.vite_amap_web_key,
      vite_amap_web_js_key: settingsForm.vite_amap_web_js_key,
      google_maps_api_key: settingsForm.google_maps_api_key,
      google_maps_proxy: settingsForm.google_maps_proxy,
      xhs_cookie: settingsForm.xhs_cookie,
      openai_api_key: settingsForm.openai_api_key,
      openai_base_url: settingsForm.openai_base_url,
      openai_model: settingsForm.openai_model,
    }
    const saved = await saveRuntimeSettings(payload)
    applyRuntimeSettings(saved)
    message.success(t('settings.messages.saved'))
    settingsVisible.value = false
  } catch (error: any) {
    message.error(error?.message || t('settings.messages.saveFailed'))
  } finally {
    settingsSaving.value = false
  }
}
</script>
<style scoped>
.travel-nav { position: sticky; top: 0; z-index: 100; width: 100%; background: rgba(255,255,255,.96); border-bottom: 1px solid var(--travel-border); backdrop-filter: blur(16px); }
.nav-inner { max-width: 1280px; margin: auto; min-height: 76px; padding: 0 36px; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.brand { display: inline-flex; align-items: center; gap: 11px; border: 0; background: transparent; color: var(--travel-ink); font-size: 19px; font-weight: 700; white-space: nowrap; padding: 0; }
.nav-actions { display: flex; align-items: center; gap: 14px; }
.lang-select-nav { width: 100px; }
.lang-select-nav :deep(.ant-select-selector) { border: 0 !important; background: transparent !important; box-shadow: none !important; }
.settings-btn { display: flex; align-items: center; gap: 6px; padding: 8px; color: var(--travel-muted); border: 0; background: transparent; font-size: 13px; }
.nav-cta { padding: 11px 18px; border: 0; border-radius: 9px; background: var(--travel-accent); color: white; font-size: 13px; font-weight: 600; }
.nav-cta span { margin-left: 12px; }
.nav-cta:hover { background: #155241; }
@media (max-width: 600px) { .nav-inner { padding: 0 16px; min-height: 66px; gap: 8px; } .brand { font-size: 15px; gap: 7px; } .brand img { width: 28px; height: 28px; } .nav-actions { gap: 4px; } .settings-btn span, .nav-cta { display: none; } .lang-select-nav { width: 84px; } }
</style>
