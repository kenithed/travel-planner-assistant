<template>
  <div class="swiper-slide" :class="{ 'swiper-slide-active': active }" @mouseenter="emit('hover')" @focusin="emit('hover')">
    <div class="swiper-slide-img"><img :src="imageSrc" :alt="item.name" loading="lazy" @error="emit('image-error', $event)" /><span>{{ t('common.dayNumber', { day: item.dayArrayIndex + 1 }) }}</span></div>
    <div class="swiper-slide-content"><h2>{{ item.name }}</h2><p>{{ item.description || item.address || t('common.noData') }}</p><button type="button" @click="emit('select-day', item.dayArrayIndex)">{{ t('result.ui.viewDay') }} <span aria-hidden="true">↗</span></button></div>
  </div>
</template>
<script setup lang="ts">
import { useI18n } from 'vue-i18n'

type OverviewAttractionItem = {
  name: string
  address: string
  visit_duration: number
  description: string
  dayArrayIndex: number
}

defineProps<{
  item: OverviewAttractionItem
  imageSrc: string
  active: boolean
}>()

const emit = defineEmits<{
  (e: 'hover'): void
  (e: 'select-day', dayArrayIndex: number): void
  (e: 'image-error', event: Event): void
}>()

const { t } = useI18n()
</script>
<style scoped>
.swiper-slide { width: 250px; height: 350px; display: flex; flex-direction: column; background: white; border: 1px solid #e0e7d8; border-radius: 14px; overflow: hidden; }
.swiper-slide-img { position: relative; width: 100%; height: 200px; flex-shrink: 0; background: #dfebde; overflow: hidden; }
.swiper-slide-img img { width: 100%; height: 100%; object-fit: cover; transition: transform .3s; }.swiper-slide:hover img { transform: scale(1.03); }
.swiper-slide-img > span { position: absolute; top: 14px; left: 14px; border-radius: 6px; padding: 5px 9px; background: rgba(255,255,255,.95); color: #416c43; font-size: 10px; }
.swiper-slide-content { padding: 17px 18px; flex: 1; display: flex; flex-direction: column; }.swiper-slide-content h2 { font-size: 16px; color: #2c4e31; margin: 0 0 8px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }.swiper-slide-content p { font-size: 11px; color: #7f9074 !important; line-height: 1.8; margin: 0 0 10px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }.swiper-slide-content button { border: 0; background: transparent; color: #39704d; text-align: left; padding: 0; font-size: 11px; margin-top: auto; display: flex; justify-content: space-between; }
</style>
