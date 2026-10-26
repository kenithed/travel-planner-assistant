<template>
  <a-config-provider :locale="componentLocale" :theme="{ token: { colorPrimary: '#1d6b58', colorText: '#203c37', colorTextSecondary: '#697970', colorBorder: '#dfe7df', borderRadius: 10, fontFamily: '-apple-system, BlinkMacSystemFont, Segoe UI, PingFang SC, Microsoft YaHei, sans-serif' } }">
    <router-view />
  </a-config-provider>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import enUS from 'ant-design-vue/es/locale/en_US'
import jaJP from 'ant-design-vue/es/locale/ja_JP'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import 'dayjs/locale/ja'
import { useI18n } from 'vue-i18n'
import { setAppLocale, type AppLocale } from '@/i18n'

const { t, locale } = useI18n()
const componentLocale = computed(() => locale.value === 'zh-CN' ? zhCN : locale.value === 'ja-JP' ? jaJP : enUS)

watch(
  locale,
  (nextLocale) => {
    setAppLocale(nextLocale as AppLocale)
    document.title = t('app.title')
    document.documentElement.lang = nextLocale
    dayjs.locale(nextLocale === 'zh-CN' ? 'zh-cn' : nextLocale === 'ja-JP' ? 'ja' : 'en')
  },
  { immediate: true }
)
</script>
