<template>
  <div class="landing-page">
    <NavBar @brand-click="scrollToTop" @cta-click="scrollToForm" />
    <main>
      <section class="travel-hero">
        <div class="hero-copy">
          <p class="eyebrow"><span></span> {{ t('home.heroBadge') }}</p>
          <h1>{{ t('home.titleLine') }}<br /><em>{{ t('home.ui.titleAccent') }}</em></h1>
          <p class="hero-description">{{ t('home.heroDesc') }}</p>
          <button type="button" class="hero-cta" @click="scrollToForm">{{ t('home.nav.cta') }} <span aria-hidden="true">↗</span></button>
          <div class="hero-features"><span>{{ t('home.ui.feature1') }}</span><i></i><span>{{ t('home.ui.feature2') }}</span><i></i><span>{{ t('home.ui.feature3') }}</span></div>
        </div>
        <div class="journey-visual" aria-hidden="true">
          <div class="visual-caption"><span>YOUR NEXT JOURNEY</span><span>↗</span></div>
          <svg viewBox="0 0 480 290" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M-30 220C90 140 5 10 178-15L331 0C263 51 377 95 480 71V290H-30Z" fill="#dce8d9"/>
            <path d="M255-10C165 80 351 118 294 190S225 272 250 320" stroke="#b9d9d2" stroke-width="38"/>
            <path d="M-20 248 142 83 216 98 363 12M21 300 176 153 301 161 490 251M155-20 158 65 49 146 3 136M358 290 377 185 491 128" stroke="#f7faf5" stroke-width="14"/>
            <path d="M109 216C139 212 113 121 179 116S291 222 364 91" stroke="#27745c" stroke-width="3" stroke-dasharray="7 7"/>
            <circle cx="109" cy="216" r="11" fill="#1d6b58" stroke="white" stroke-width="5"/><circle cx="179" cy="116" r="9" fill="#1d6b58" stroke="white" stroke-width="5"/>
            <path d="M364 57c-14 0-25 11-25 25 0 19 25 41 25 41s25-22 25-41c0-14-11-25-25-25Z" fill="#1d6b58"/><circle cx="364" cy="81" r="8" fill="#f2f6eb"/>
            <path d="m54 61 17-25 17 25H77v15H65V61ZM405 224l17-25 17 25h-11v15h-12v-15Z" fill="#90b6a1"/>
          </svg>
          <div class="visual-note"><span class="note-icon">✧</span><div><strong>{{ t('home.ui.visualTitle') }}</strong><p>{{ t('home.ui.visualDesc') }}</p></div></div>
        </div>
      </section>
      <div class="planning-layout">
    <section ref="formRef" class="form-section">
      <div class="form-panel" :style="{ minHeight: panelHeight === 'auto' ? 'auto' : panelHeight + 'px' }" ref="panelRef">
        <div class="form-heading" v-show="!loading"><div><p class="eyebrow">{{ t('home.ui.formEyebrow') }}</p><h2>{{ t('home.ui.formTitle') }}</h2></div><span class="form-count">03 / STEPS</span></div>
        <a-form v-show="!loading" :model="formData" layout="vertical" @finish="handleSubmit">
          <div class="step">
            <div class="step-head">
              <span>01</span>
              <h3>{{ t('home.step1') }}</h3>
            </div>

            <!-- 多城市动态列表 -->
            <div class="city-list">
              <div v-for="(cs, idx) in formData.cities" :key="idx" class="city-row">
                <a-form-item class="city-row-name" :name="['cities', idx, 'city']" :rules="[{ required: true, message: t('home.cityRequired') }]">
                  <template #label>
                    <span class="field-label">{{ t('home.cityNLabel', { n: idx + 1 }) }}</span>
                  </template>
                  <a-input
                    v-model:value="cs.city"
                    :placeholder="t('home.cityPlaceholder')"
                    size="large"
                    class="field-input"
                  />
                </a-form-item>
                <a-form-item class="city-row-days">
                  <template #label>
                    <span class="field-label">{{ t('home.cityStayDays') }}</span>
                  </template>
                  <a-input-number
                    v-model:value="cs.days"
                    :min="1"
                    :max="15"
                    size="large"
                    class="field-input"
                    style="width: 100%"
                  />
                </a-form-item>
                <button
                  v-if="formData.cities.length > 1"
                  type="button"
                  class="city-remove-btn" :aria-label="t('home.removeCity') + ' ' + (idx + 1)"
                  @click="removeCity(idx)"
                >×</button>
              </div>
              <button type="button" class="city-add-btn" :disabled="formData.cities.length >= 5" @click="addCity">
                + {{ t('home.addCity') }}
              </button>
            </div>

            <!-- 日期与天数 -->
            <div class="grid grid-date">
              <a-form-item name="start_date" :rules="formRules.startDate">
                <template #label>
                  <span class="field-label">{{ t('home.startDateLabel') }}</span>
                </template>
                <a-date-picker
                  v-model:value="formData.start_date"
                  style="width: 100%"
                  size="large"
                  class="field-input"
                  :placeholder="t('home.startDatePlaceholder')"
                />
              </a-form-item>

              <a-form-item>
                <template #label>
                  <span class="field-label">{{ t('home.travelDaysLabel') }}</span>
                </template>
                <div class="days-chip">
                  <span class="days-number">{{ totalDays }}</span>
                  <span class="days-unit">{{ t('home.travelDaysUnit') }}</span>
                </div>
              </a-form-item>
            </div>
          </div>

          <div class="step">
            <div class="step-head">
              <span>02</span>
              <h3>{{ t('home.step2') }}</h3>
            </div>
            <div class="grid grid2">
              <a-form-item name="transportation">
                <template #label>
                  <span class="field-label">{{ t('home.transportationLabel') }}</span>
                </template>
                <a-select v-model:value="formData.transportation" size="large" class="field-select">
                  <a-select-option value="公共交通">{{ t('home.transportation.public') }}</a-select-option>
                  <a-select-option value="自驾">{{ t('home.transportation.drive') }}</a-select-option>
                  <a-select-option value="步行">{{ t('home.transportation.walk') }}</a-select-option>
                  <a-select-option value="混合">{{ t('home.transportation.mixed') }}</a-select-option>
                </a-select>
              </a-form-item>

              <a-form-item name="accommodation">
                <template #label>
                  <span class="field-label">{{ t('home.accommodationLabel') }}</span>
                </template>
                <a-select v-model:value="formData.accommodation" size="large" class="field-select">
                  <a-select-option value="经济型酒店">{{ t('home.accommodation.budget') }}</a-select-option>
                  <a-select-option value="舒适型酒店">{{ t('home.accommodation.comfort') }}</a-select-option>
                  <a-select-option value="豪华酒店">{{ t('home.accommodation.luxury') }}</a-select-option>
                  <a-select-option value="民宿">{{ t('home.accommodation.homestay') }}</a-select-option>
                </a-select>
              </a-form-item>
            </div>

            <a-form-item name="preferences">
              <template #label>
                <span class="field-label">{{ t('home.interestsLabel') }}</span>
              </template>
              <div class="interest-grid">
                <div class="interest-group" role="group" :aria-label="t('home.interestsLabel')">
                  <button type="button"
                    v-for="item in interestOptions"
                    :key="item.value"
                    class="interest-pill"
                    :class="{ active: formData.preferences.includes(item.value) }"
                    :aria-pressed="formData.preferences.includes(item.value)" @click="togglePreference(item.value)"
                  >
                    {{ t(item.labelKey) }}
                  </button>
                </div>
              </div>
            </a-form-item>
          </div>

          <div class="step">
            <div class="step-head">
              <span>03</span>
              <h3>{{ t('home.step3') }}</h3>
            </div>
            <a-form-item name="free_text_input">
              <div class="need-examples"><button v-for="key in ['budget', 'pace', 'indoor']" :key="key" type="button" @click="appendNeed(t('home.ui.examples.' + key))">+ {{ t('home.ui.exampleLabels.' + key) }}</button></div>
              <div class="field-textarea">
                <a-textarea
                  v-model:value="formData.free_text_input"
                  :placeholder="t('home.specialNeedsPlaceholder')"
                  :rows="4" :aria-label="t('home.step3')"
                  size="large"
                  class="special-textarea"
                />
              </div>
            </a-form-item>
          </div>

          <p class="form-help">{{ t('home.ui.requirementsHint') }}</p>
          <a-form-item class="submit-item">
            <button type="submit" class="btn btn-danger btn-round submit-btn" :class="{ loading }" :disabled="loading">
              <span v-if="!loading">{{ t('home.submit') }}</span>
              <span v-else class="loading-row">
                <i class="spinner"></i>
                {{ t('home.submitting') }}
              </span>
            </button>
          </a-form-item>
        </a-form>

        <!-- Node Loading Stepper -->
        <div v-show="loading" class="stepper-wrapper" role="status" aria-live="polite" :aria-busy="loading">
          <div class="stepper-header">
            <h2 class="stepper-title">{{ t('home.loading.planCode', { code: planCode }) }}</h2>
            <p class="stepper-subtitle">{{ t('home.loading.preparing') }}</p>
          </div>
          
          <div class="stepper-container">
            <!-- Step 1: Searching Attractions -->
            <div class="step-node" :class="{ active: loadingProgress >= 0 && loadingProgress <= 30, completed: loadingProgress > 30 }">
              <div class="node-icon">
                <i v-if="loadingProgress >= 0 && loadingProgress <= 30" class="spinner-small"></i>
                <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
              </div>
              <p class="node-text">{{ loadingProgress > 30 ? t('home.loading.searchedAttractions') : t('home.loading.searchingAttractions') }}</p>
            </div>
            <div class="step-divider" :class="{ completed: loadingProgress > 30 }"></div>

            <!-- Step 2: Weather -->
            <div class="step-node" :class="{ active: loadingProgress > 30 && loadingProgress <= 50, completed: loadingProgress > 50 }">
              <div class="node-icon">
                <i v-if="loadingProgress > 30 && loadingProgress <= 50" class="spinner-small"></i>
                <svg v-else width="20px" height="20px" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                  <path d="M10.5 1.5V3.1M3.6 10H2M5.4512 4.95137L4.31982 3.82M15.5498 4.95137L16.6812 3.82M19 10H17.4M6.50007 10.0001C6.50007 7.79093 8.29093 6.00007 10.5001 6.00007C12.0061 6.00007 13.3177 6.83235 14.0001 8.06206M6 22C3.79086 22 2 20.2091 2 18C2 15.7909 3.79086 14 6 14C6.46419 14 6.90991 14.0791 7.32442 14.2245C8.04061 12.3396 9.86387 11 12 11C14.1361 11 15.9594 12.3396 16.6756 14.2245C17.0901 14.0791 17.5358 14 18 14C20.2091 14 22 15.7909 22 18C22 20.2091 20.2091 22 18 22C13.3597 22 9.87921 22 6 22Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </div>
              <p class="node-text">{{ loadingProgress > 50 ? t('home.loading.queriedWeather') : t('home.loading.queryingWeather') }}</p>
            </div>
            <div class="step-divider" :class="{ completed: loadingProgress > 50 }"></div>

            <!-- Step 3: Hotels -->
            <div class="step-node" :class="{ active: loadingProgress > 50 && loadingProgress <= 70, completed: loadingProgress > 70 }">
              <div class="node-icon">
                <i v-if="loadingProgress > 50 && loadingProgress <= 70" class="spinner-small"></i>
                <svg v-else fill="currentColor" width="25px" height="25px" viewBox="0 0 24 24" version="1.1" xml:space="preserve" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
                    <g id="Layer_Grid"/><g id="Layer_2">
                    <path d="M21,8c0-2.2-1.8-4-4-4H7C4.8,4,3,5.8,3,8v3.8c-0.6,0.5-1,1.3-1,2.2v2.7V17v2c0,0.6,0.4,1,1,1s1-0.4,1-1v-1h16v1   c0,0.6,0.4,1,1,1s1-0.4,1-1v-2v-0.3V14c0-0.9-0.4-1.7-1-2.2V8z M5,8c0-1.1,0.9-2,2-2h10c1.1,0,2,0.9,2,2v3h-1v-1c0-1.7-1.3-3-3-3   h-1c-0.8,0-1.5,0.3-2,0.8C11.5,7.3,10.8,7,10,7H9c-1.7,0-3,1.3-3,3v1H5V8z M16,10v1h-3v-1c0-0.6,0.4-1,1-1h1C15.6,9,16,9.4,16,10z    M11,10v1H8v-1c0-0.6,0.4-1,1-1h1C10.6,9,11,9.4,11,10z M20,16H4v-2c0-0.6,0.4-1,1-1h3h3h2h3h3c0.6,0,1,0.4,1,1V16z"/></g>
                </svg>
              </div>
              <p class="node-text">{{ loadingProgress > 70 ? t('home.loading.recommendedHotels') : t('home.loading.recommendingHotels') }}</p>
            </div>
            <div class="step-divider" :class="{ completed: loadingProgress > 70 }"></div>

            <!-- Step 4: Planning -->
            <div class="step-node" :class="{ active: loadingProgress > 70 && loadingProgress < 100, completed: loadingProgress >= 100 }">
              <div class="node-icon">
                <i v-if="loadingProgress > 70 && loadingProgress < 100" class="spinner-small"></i>
                <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"></polyline><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>
              </div>
              <p class="node-text">{{ loadingProgress >= 100 ? t('home.loading.done') : t('home.loading.generatingPlan') }}</p>
            </div>
          </div>
          
          <div class="stepper-footer">
            <h3>{{ loadingStatus }}</h3>
            <p v-if="loadingProgress < 100">{{ t('home.loading.workingTogether') }}</p>
            <p v-else>{{ t('home.loading.donePrepare') }}</p>
          </div>
        </div>
      </div>
    </section>
        <aside class="trip-sidebar">
          <div class="summary-panel">
            <p class="eyebrow">{{ t('home.ui.summaryEyebrow') }}</p><h2>{{ t('home.ui.summaryTitle') }}</h2>
            <div class="summary-route"><div v-for="(city, index) in formData.cities" :key="index"><span class="route-dot"></span><strong>{{ city.city || t('home.ui.pendingCity') }}</strong><span>{{ t('common.dayCount', { count: city.days || 1 }) }}</span></div></div>
            <dl><div><dt>{{ t('home.startDateLabel') }}</dt><dd>{{ formData.start_date?.format('YYYY-MM-DD') || t('home.ui.pendingDate') }}</dd></div><div><dt>{{ t('home.endDateLabel') }}</dt><dd>{{ computedEndDate?.format('YYYY-MM-DD') || '—' }}</dd></div><div><dt>{{ t('home.travelDaysLabel') }}</dt><dd class="summary-total">{{ t('common.dayCount', { count: totalDays }) }}</dd></div></dl>
            <p class="summary-tip">{{ t('home.ui.summaryHint') }}</p>
          </div>
          <div class="guide-panel"><span class="guide-icon" aria-hidden="true">↗</span><h3>{{ t('home.ui.guideTitle') }}</h3><p>{{ t('home.ui.guideDesc') }}</p><div>{{ t('home.ui.guideFoot') }}</div></div>
        </aside>
      </div>

    <section class="history-section">
      <div class="history-panel">
        <div class="history-head">
          <div>
            <p class="history-eyebrow">{{ t('home.history.eyebrow') }}</p>
            <h3 class="history-title">{{ t('home.history.title') }}</h3>
          </div>
          <a-button type="link" class="history-refresh" @click="loadHistoryPlans">
            {{ t('home.history.refresh') }}
          </a-button>
        </div>

        <div v-if="historyLoading" class="history-loading">
          {{ t('common.loading') }}
        </div>
        <a-empty v-else-if="historyPlans.length === 0" :description="t('home.history.empty')" />
        <div v-else class="history-list">
          <button
            v-for="item in historyPlans"
            :key="item.plan_id"
            type="button"
            class="history-item"
            @click="openHistoryPlan(item.plan_id)"
          >
            <div class="history-item-main">
              <div class="history-route">
                <span class="history-city">{{ item.city }}</span>
                <span class="history-date">{{ item.start_date }} {{ t('common.to') }} {{ item.end_date }}</span>
              </div>
              <p class="history-meta">
                <span>{{ item.travel_days }}{{ t('home.travelDaysUnit') }}</span>
                <span>{{ t('home.history.updatedAt') }} {{ formatHistoryTime(item.updated_at) }}</span>
              </p>
              <p v-if="item.overall_suggestions" class="history-summary">{{ item.overall_suggestions }}</p>
            </div>
            <span class="history-open">{{ t('home.history.open') }}</span>
          </button>
        </div>
      </div>
    </section>
    </main>
    <footer class="travel-footer"><span>{{ t('app.brand') }}</span><p>{{ t('home.ui.footer') }}</p><a href="https://github.com/1sdv/TripStar" target="_blank" rel="noopener noreferrer">{{ t('home.ui.source') }} ↗</a></footer>
  </div>
</template>


<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { generateTripPlan, getTripHistory } from '@/services/api'
import { getCurrentLocale } from '@/i18n'
import NavBar from '@/components/NavBar.vue'
import type { TripFormData, TripTaskEvent, TripHistoryItem, CityStay } from '@/types'
import type { Dayjs } from 'dayjs'

type LandingFormData = {
  cities: Array<{ city: string; days: number }>
  start_date: Dayjs | null
  transportation: string
  accommodation: string
  preferences: string[]
  free_text_input: string
}

const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const loadingProgress = ref(0)
const loadingStatus = ref('')
const formRef = ref<HTMLElement | null>(null)
const panelRef = ref<HTMLElement | null>(null)
const panelHeight = ref<number | string>('auto')
const planCode = ref('')
const historyLoading = ref(false)
const historyPlans = ref<TripHistoryItem[]>([])

const getStageStatusText = (stage: TripTaskEvent['stage']) => {
  if (stage === 'submitted' || stage === 'initializing') return t('home.loading.initializing')
  if (stage === 'attraction_search') return t('home.loading.searchingAttractions')
  if (stage === 'weather_search') return t('home.loading.queryingWeather')
  if (stage === 'hotel_search') return t('home.loading.recommendingHotels')
  if (stage === 'planning') return t('home.loading.generatingPlan')
  if (stage === 'graph_building') return t('home.loading.generatingPlan')
  if (stage === 'completed') return t('home.loading.done')
  return t('home.loading.initializing')
}

const interestOptions = [
  { value: '历史文化', labelKey: 'home.interests.history' },
  { value: '自然风光', labelKey: 'home.interests.nature' },
  { value: '美食', labelKey: 'home.interests.food' },
  { value: '购物', labelKey: 'home.interests.shopping' },
  { value: '艺术', labelKey: 'home.interests.art' },
  { value: '休闲', labelKey: 'home.interests.leisure' },
]

const formRules = computed(() => ({
  startDate: [{ required: true, message: t('home.startDateRequired') }],
}))

const formData = reactive<LandingFormData>({
  cities: [{ city: '', days: 2 }],
  start_date: null,
  transportation: '公共交通',
  accommodation: '经济型酒店',
  preferences: [],
  free_text_input: '',
})

const totalDays = computed(() => formData.cities.reduce((sum, cs) => sum + (cs.days || 1), 0))

const computedEndDate = computed(() => {
  if (!formData.start_date) return null
  return formData.start_date.add(totalDays.value - 1, 'day')
})

const addCity = () => {
  if (formData.cities.length >= 5) return
  formData.cities.push({ city: '', days: 2 })
}

const removeCity = (index: number) => {
  if (formData.cities.length <= 1) return
  formData.cities.splice(index, 1)
}

const appendNeed = (text: string) => {
  if (!formData.free_text_input.includes(text)) {
    formData.free_text_input = [formData.free_text_input.trim(), text].filter(Boolean).join('；')
  }
}

const togglePreference = (value: string) => {
  const index = formData.preferences.indexOf(value)
  if (index === -1) formData.preferences.push(value)
  else formData.preferences.splice(index, 1)
}

const scrollToTop = () => window.scrollTo({ top: 0, behavior: 'smooth' })
const scrollToForm = () => {
  if (formRef.value) {
    const y = formRef.value.getBoundingClientRect().top + window.scrollY - 65
    window.scrollTo({ top: y, behavior: 'smooth' })
  }
}

const formatHistoryTime = (value: string) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

const openHistoryPlan = (planId: string) => {
  if (!planId) return
  sessionStorage.removeItem('tripPlan')
  sessionStorage.removeItem('graphData')
  sessionStorage.setItem('planId', planId)
  router.push({ path: '/result', query: { plan_id: planId } })
}

const loadHistoryPlans = async () => {
  historyLoading.value = true
  try {
    historyPlans.value = await getTripHistory(8)
  } catch (error: any) {
    historyPlans.value = []
    message.error(error.message || t('home.history.loadFailed'))
  } finally {
    historyLoading.value = false
  }
}

onMounted(() => {
  void loadHistoryPlans()
})


const handleSubmit = async () => {
  // 校验：至少一个城市名非空
  const validCities = formData.cities.filter(cs => cs.city.trim())
  if (validCities.length === 0) {
    message.error(t('home.atLeastOneCity'))
    return
  }
  if (!formData.start_date) {
    message.error(t('home.messages.selectDate'))
    return
  }
  if (totalDays.value > 30) {
    message.warning(t('home.messages.travelDaysTooLong'))
    return
  }

  if (panelRef.value) {
    panelHeight.value = panelRef.value.offsetHeight
  }

  loading.value = true
  loadingProgress.value = 5
  loadingStatus.value = t('home.loading.initializing')
  planCode.value = ''

  try {
    sessionStorage.removeItem('tripPlan')
    sessionStorage.removeItem('graphData')
    sessionStorage.removeItem('planId')

    const citiesPayload: CityStay[] = validCities.map(cs => ({ city: cs.city.trim(), days: cs.days || 1 }))
    const endDate = computedEndDate.value!

    const requestData: TripFormData = {
      city: citiesPayload[0].city,
      cities: citiesPayload,
      start_date: formData.start_date.format('YYYY-MM-DD'),
      end_date: endDate.format('YYYY-MM-DD'),
      travel_days: totalDays.value,
      transportation: formData.transportation,
      accommodation: formData.accommodation,
      preferences: formData.preferences,
      free_text_input: formData.free_text_input,
      language: getCurrentLocale(),
    }

    const response = await generateTripPlan(requestData, {
      onTaskCreated: (task) => {
        planCode.value = task.plan_id || task.task_id
        loadingProgress.value = 5
        loadingStatus.value = t('home.loading.initializing')
      },
      onTaskEvent: (event) => {
        if (event.plan_id) planCode.value = event.plan_id
        if (Number.isFinite(event.progress)) {
          loadingProgress.value = Math.max(0, Math.min(100, event.progress))
        }
        loadingStatus.value = event.message || getStageStatusText(event.stage)
      }
    })

    loadingProgress.value = 100
    loadingStatus.value = t('home.loading.done')

    if (response.success && response.data) {
      const planId = response.plan_id || planCode.value
      sessionStorage.setItem('tripPlan', JSON.stringify(response.data))
      if (response.graph_data) sessionStorage.setItem('graphData', JSON.stringify(response.graph_data))
      if (planId) sessionStorage.setItem('planId', planId)
      message.success(t('home.messages.generateSuccess'))
      setTimeout(() => {
        if (planId) {
          router.push({ path: '/result', query: { plan_id: planId } })
        } else {
          router.push('/result')
        }
      }, 500)
    } else {
      sessionStorage.removeItem('tripPlan')
      sessionStorage.removeItem('graphData')
      sessionStorage.removeItem('planId')
      message.error(response.message || t('home.messages.generateFailed'))
    }
  } catch (error: any) {
    sessionStorage.removeItem('tripPlan')
    sessionStorage.removeItem('graphData')
    sessionStorage.removeItem('planId')
    message.error(error.message || t('home.messages.generateRetry'))
  } finally {
    setTimeout(() => {
      loading.value = false
      loadingProgress.value = 0
      loadingStatus.value = ''
      panelHeight.value = 'auto'
    }, 1000)
  }
}
</script>
<style scoped>
.landing-page { background: #f5f7f3; color: var(--travel-ink); min-height: 100vh; }
main { max-width: 1208px; margin: auto; padding: 0 0 60px; }
.travel-hero { display: grid; grid-template-columns: 1.1fr .9fr; gap: 60px; align-items: center; padding: 60px 0 56px; }
.eyebrow { color: #678171; font-size: 11px; font-weight: 600; letter-spacing: .13em; line-height: 1.6; }
.hero-copy .eyebrow { display: flex; align-items: center; gap: 8px; margin-bottom: 18px; }
.hero-copy .eyebrow span { width: 6px; height: 6px; background: #398668; border-radius: 50%; }
h1 { font-size: clamp(32px,3.3vw,46px); line-height: 1.4; font-weight: 600; letter-spacing: -.04em; margin: 0; }
h1 em { font-style: normal; color: var(--travel-accent); }
.hero-description { color: var(--travel-muted); font-size: 14px; line-height: 1.9; margin: 18px 0 23px; max-width: 450px; }
.hero-cta { border: 0; border-radius: 9px; padding: 13px 21px; background: var(--travel-accent); color: white; font-size: 14px; font-weight: 600; }
.hero-cta span { margin-left: 34px; }
.hero-features { display: flex; align-items: center; gap: 12px; font-size: 11px; color: #7a877c; margin-top: 20px; }
.hero-features i { width: 3px; height: 3px; background: #acb9ac; border-radius: 50%; }
.journey-visual { position: relative; background: #eaf0e5; border: 1px solid #d8e3d5; border-radius: 22px; overflow: hidden; transform: rotate(-2deg); box-shadow: 0 14px 35px #264d3010; }
.visual-caption { display: flex; justify-content: space-between; padding: 23px 26px 0; font-size: 10px; letter-spacing: .16em; color: #5a7c69; }
.journey-visual svg { width: 100%; display: block; }
.visual-note { position: absolute; bottom: 20px; left: 20px; right: 20px; padding: 16px; background: rgba(255,255,255,.95); border: 1px solid white; border-radius: 12px; display: flex; align-items: center; gap: 12px; box-shadow: 0 8px 28px #1d462410; }
.note-icon { font-size: 24px; padding: 5px 12px; background: #f0f4e9; border-radius: 10px; color: #60854f; }
.visual-note strong { font-size: 14px; }.visual-note p { font-size: 11px; color: #7c887c; margin: 5px 0 0; }
.planning-layout { display: grid; grid-template-columns: minmax(0,1fr) 300px; gap: 24px; align-items: start; }
.form-section { scroll-margin-top: 100px; min-width: 0; }
.form-panel { border: 1px solid var(--travel-border); border-radius: 18px; background: white; padding: 32px; box-shadow: 0 5px 20px #2d4a3503; }
.form-heading { display: flex; justify-content: space-between; align-items: center; margin-bottom: 32px; }.form-heading h2 { font-size: 23px; font-weight: 600; margin-top: 6px; }.form-count { color: #9ba69a; font-size: 10px; letter-spacing: .1em; }
.step { margin-bottom: 26px; }.step + .step { padding-top: 26px; border-top: 1px solid #eef1eb; }
.step-head { display: flex; align-items: center; gap: 10px; margin-bottom: 20px; }.step-head > span { background: #edf3ec; color: #417358; font-size: 10px; font-weight: 700; width: 28px; height: 28px; display: grid; place-items: center; border-radius: 8px; }.step-head h3 { font-size: 16px; font-weight: 600; margin: 0; }
.field-label { font-size: 12px; color: #5d6f63; }.form-panel :deep(.ant-form-item) { margin-bottom: 17px; }.form-panel :deep(.ant-form-item-label) { padding-bottom: 7px; }.form-panel :deep(.ant-input), .form-panel :deep(.ant-picker), .form-panel :deep(.ant-input-number), .form-panel :deep(.ant-select-selector) { font-size: 13px !important; background: #fcfdfb; border-radius: 9px; }.form-panel :deep(.ant-select-selection-item) { line-height: 38px; }.form-panel :deep(.ant-select) { width: 100%; }
.city-row { display: flex; align-items: flex-start; gap: 12px; }.city-row-name { flex: 1; min-width: 0; }.city-row-days { width: 120px; flex: 0 0 120px; }.city-remove-btn { margin-top: 30px; width: 32px; height: 40px; border: 1px solid #ead9d2; background: #fffaf8; color: #a2604f; border-radius: 8px; }
.city-add-btn { background: transparent; border: 1px dashed #b5cbb9; border-radius: 8px; color: #507d61; width: 100%; padding: 9px; font-size: 12px; margin-bottom: 20px; }.city-add-btn:hover { background: #f4f8f0; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }.days-chip { display: flex; align-items: center; gap: 8px; height: 40px; border: 1px solid #e4eadd; border-radius: 8px; padding: 0 14px; background: #f3f6ee; }.days-number { font-size: 18px; font-weight: 600; }.days-unit { color: #7b8975; font-size: 12px; }
.interest-group { display: flex; flex-wrap: wrap; gap: 9px; }.interest-pill { background: white; border: 1px solid #e1e7df; padding: 9px 15px; font-size: 12px; color: #69796b; border-radius: 8px; }.interest-pill.active { background: #e9f3eb; border-color: #70a280; color: #275d40; }.interest-pill:hover { border-color: #82a78c; }
.need-examples { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }.need-examples button { background: #f4f6f0; border: 0; border-radius: 5px; font-size: 11px; color: #6d8168; padding: 6px 10px; }.special-textarea { line-height: 1.8; padding: 13px; }.form-help { font-size: 11px; line-height: 1.8; color: #86907e; margin: -12px 0 20px; }
.submit-btn { width: 100%; padding: 14px; border: 0; border-radius: 9px; background: #1d6b58; color: white; font-size: 14px; font-weight: 600; }.submit-btn:hover { background: #155241; }.form-panel :deep(.submit-item) { margin: 0; }
.trip-sidebar { position: sticky; top: 100px; }.summary-panel { border: 1px solid #d8e2d5; background: #f0f4eb; border-radius: 18px; padding: 26px; }.summary-panel h2 { font-size: 20px; margin: 6px 0 24px; font-weight: 600; }.summary-route { display: grid; gap: 20px; margin-bottom: 24px; }.summary-route > div { display: flex; align-items: center; gap: 10px; font-size: 13px; }.route-dot { background: #5f9675; border: 3px solid #d9e7d5; height: 13px; width: 13px; border-radius: 50%; flex-shrink: 0; }.summary-route strong { flex: 1; overflow-wrap: anywhere; }.summary-route div > span:last-child { font-size: 12px; color: #7d8d76; white-space: nowrap; }
dl { margin: 0; border-top: 1px solid #dce5d7; padding: 15px 0; }dl > div { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 8px 0; }dt { font-size: 12px; color: #7d8a75; }dd { margin: 0; font-size: 12px; font-weight: 500; }.summary-total { font-size: 21px; color: #326344; }.summary-tip { border-top: 1px solid #dce5d7; padding-top: 17px; color: #84907d; font-size: 11px; line-height: 1.8; }
.guide-panel { padding: 28px 20px; }.guide-icon { display: block; margin-bottom: 13px; font-size: 25px; color: #a1ac8a; }.guide-panel h3 { font-size: 14px; margin-bottom: 10px; }.guide-panel p { font-size: 12px; color: #7c8978; line-height: 1.9; }.guide-panel > div { font-size: 10px; margin-top: 20px; color: #9ba18c; }
.history-section { margin-top: 48px; }.history-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }.history-eyebrow { font-size: 10px; color: #85937e; letter-spacing: .13em; margin-bottom: 5px; }.history-title { font-size: 22px; font-weight: 600; }.history-list { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }.history-item { border: 1px solid #e0e6db; border-radius: 13px; padding: 21px; background: white; text-align: left; display: flex; gap: 15px; align-items: center; transition: border-color .2s, transform .2s; }.history-item:hover { border-color: #97b79c; transform: translateY(-2px); }.history-item-main { min-width: 0; flex: 1; }.history-route { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }.history-city { font-size: 15px; font-weight: 600; }.history-date { font-size: 10px; color: #7f8d7c; }.history-meta { display: flex; flex-wrap: wrap; gap: 10px; font-size: 10px; color: #99a092; margin-top: 8px; }.history-summary { font-size: 11px; line-height: 1.7; color: #7d8976; margin-top: 9px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }.history-open { font-size: 11px; color: #497453; white-space: nowrap; }.history-loading { padding: 40px; text-align: center; color: #6d806f; }
.travel-footer { display: flex; align-items: center; gap: 22px; border-top: 1px solid #e0e6db; padding: 26px max(24px,calc((100vw - 1208px)/2)); font-size: 11px; color: #8d9786; }.travel-footer > span { color: #496449; font-weight: 600; }.travel-footer a { margin-left: auto; color: #7c8e76; text-decoration: none; }
.stepper-wrapper { padding: 40px 0; }.stepper-header { text-align: center; }.stepper-title { font-size: 22px; }.stepper-subtitle { font-size: 13px; color: #7c8a77; margin-top: 12px; }.stepper-container { display: flex; align-items: flex-start; margin: 60px 0; }.step-node { text-align: center; flex: 1; font-size: 11px; color: #94a08c; }.node-icon { height: 44px; width: 44px; border-radius: 50%; background: #eff3ea; margin: 0 auto 14px; display: grid; place-items: center; }.step-node.active, .step-node.completed { color: #1d6b58; }.step-node.active .node-icon, .step-node.completed .node-icon { background: #dbeee0; }.step-divider { height: 2px; flex: .35; margin-top: 22px; background: #e1e8dc; }.step-divider.completed { background: #559477; }.stepper-footer { text-align: center; }.stepper-footer h3 { font-size: 15px; }.stepper-footer p { font-size: 12px; color: #85917d; margin-top: 10px; }.spinner-small,.spinner { display: inline-block; height: 17px; width: 17px; border: 2px solid #b8d0b5; border-top-color: #1d6b58; border-radius: 50%; animation: spin 1s linear infinite; }@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 1280px) { main { padding-left: 36px; padding-right: 36px; }.travel-hero { gap: 40px; } }
@media (max-width: 960px) { .planning-layout { grid-template-columns: minmax(0,1fr) 260px; gap: 18px; }.form-panel { padding: 24px; }.travel-hero { gap: 30px; padding-top: 40px; }.hero-features { gap: 8px; }.summary-panel { padding: 20px; } }
@media (max-width: 760px) { main { padding: 0 20px 40px; }.travel-hero { grid-template-columns: 1fr; padding: 34px 0 30px; gap: 28px; }.hero-copy h1 { font-size: 35px; }.journey-visual { display: none; }.planning-layout { grid-template-columns: 1fr; }.trip-sidebar { position: static; }.summary-panel { padding: 22px; }.guide-panel { display: none; }.history-list { grid-template-columns: 1fr; }.history-section { margin-top: 34px; }.travel-footer { flex-wrap: wrap; padding: 24px 20px; gap: 12px; }.travel-footer p { flex-basis: 100%; order: 2; } }
@media (max-width: 420px) { .form-count { display: none; }.form-heading h2 { font-size: 21px; } main { padding-left: 14px; padding-right: 14px; }.form-panel { padding: 21px 16px; }.grid { gap: 12px; }.city-row-days { width: 83px; flex-basis: 83px; }.city-row { gap: 8px; }.interest-pill { padding: 8px 12px; }.history-item { padding: 17px; }.history-date { font-size: 10px; }.history-open { display: none; } }

</style>
