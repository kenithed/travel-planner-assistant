<template>
  <div class="ai-chat-floating">
    <button v-if="!chatOpen" type="button" class="chat-launcher" @click="openChatPanel" :aria-expanded="chatOpen" aria-controls="travel-chat-panel"><span aria-hidden="true">✧</span> {{ t('result.chat.toggle') }}</button>
    <section v-else id="travel-chat-panel" class="chat-panel" :aria-label="t('result.chat.title')" @keydown.esc="closeChatPanel">
      <header><div><span class="chat-avatar" aria-hidden="true">✧</span><strong>{{ t('result.chat.title') }}</strong></div><button type="button" class="chat-close-btn" :aria-label="t('common.close')" @click="closeChatPanel">×</button></header>
      <div v-if="selectedTarget" class="edit-target"><span>{{ t('common.dayNumber', {day: selectedTarget.day + 1}) }} · {{ selectedTarget.name }}</span><button type="button" @click="selectedTarget = null" :aria-label="t('result.chatEdit.clearTarget')">×</button></div>
      <p v-if="editing" class="editing-hint">{{ t('result.chatEdit.manualEditing') }}</p>
      <div class="chat-history" ref="chatMessagesRef" role="log" aria-live="polite">
        <div v-if="chatHistory.length === 0" class="chat-empty"><p>{{ t('result.chat.welcome') }}</p><div class="chat-suggestions"><button v-for="question in quickQuestions" :key="question.labelKey" type="button" :disabled="chatLoading || applying || !tripPlan || editing" @click="sendQuickQuestion(t(question.questionKey))">{{ t(question.labelKey) }} ↗</button><button type="button" :disabled="chatLoading || applying || !tripPlan || editing" @click="startReplacement(0, 0)">{{ t('result.chatEdit.tryReplace') }} ↗</button></div></div>
        <div v-for="(msg, idx) in chatHistory" :key="idx" class="chat-msg" :class="msg.role">{{ msg.content }}</div>
        <div v-if="chatLoading" class="chat-msg assistant">{{ t('result.chatEdit.searching') }}</div>
        <section v-if="proposal" class="replacement-preview" :aria-label="t('result.chatEdit.previewTitle')">
          <div class="proposal-heading"><strong>{{ t('result.chatEdit.previewTitle') }}</strong><button type="button" :disabled="applying" @click="proposal = null">{{ t('common.cancel') }}</button></div>
          <p>{{ proposal.city }} · {{ proposal.date }} · {{ proposal.radius_km }} km</p>
          <p>{{ t('result.chatEdit.anchors') }}{{ proposal.anchors.join(' / ') }}</p>
          <article v-for="candidate in proposal.candidates" :key="candidate.id" class="replacement-card">
            <h3>{{ candidate.name }}</h3><p>{{ candidate.address }}</p>
            <dl><div><dt>{{ t('result.chatEdit.fromOriginal') }}</dt><dd>{{ distanceText(candidate.distance_from_original_km) }}</dd></div><div><dt>{{ t('result.chatEdit.fromDay') }}</dt><dd>{{ distanceText(candidate.distance_from_day_km) }}</dd></div><div><dt>{{ t('result.chatEdit.detour') }}</dt><dd>{{ candidate.route_delta_km === null ? '—' : (candidate.route_delta_km > 0 ? '+' : '') + candidate.route_delta_km + ' km' }}</dd></div><div><dt>{{ t('result.budget.attraction') }}</dt><dd>{{ candidate.ticket_price === null ? t('result.chatEdit.unverified') : '¥' + candidate.ticket_price }}</dd></div></dl>
            <a :href="candidate.source_url" target="_blank" rel="noopener noreferrer">{{ candidate.source }} ↗</a>
            <p v-if="candidate.block_reason" class="candidate-warning">{{ candidate.block_reason }}</p>
            <button type="button" class="apply-replacement" :disabled="applying || editing || !candidate.can_apply" @click="applyReplacement(candidate.id)">{{ applying ? t('common.loading') : t('result.chatEdit.apply') }}</button>
          </article>
          <ul class="proposal-warnings"><li v-for="warning in proposal.warnings" :key="warning">{{ warning }}</li></ul>
          <p class="proposal-storage">{{ t('result.chatEdit.sessionOnly') }}</p>
        </section>
      </div>
      <button v-if="canUndo" type="button" class="chat-undo" :disabled="applying || chatLoading || editing" @click="emit('undo-edit')">↶ {{ t('result.chatEdit.undo') }}</button>
      <div class="chat-compose"><textarea v-model="chatInput" :aria-label="t('result.chat.placeholder')" :placeholder="chatPlaceholder" rows="3" maxlength="2000" :disabled="chatLoading || applying || !tripPlan || editing" @keydown.enter.exact.prevent="sendChatMessage"></textarea><button type="button" :disabled="chatLoading || applying || !chatInput.trim() || !tripPlan || editing" @click="sendChatMessage">{{ t('result.chat.send') }} ↑</button></div>
    </section>
  </div>
</template>
<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import type { ChatMessage, TripPlan, TripChatResponse, ReplacementProposal, TripEditResult } from '@/types'
import { getRuntimeApiBaseUrl } from '@/services/api'
import { getCurrentLocale } from '@/i18n'

const props = defineProps<{ tripPlan: TripPlan | null; editing?: boolean; canUndo?: boolean }>()
const emit = defineEmits<{
  (event: 'apply-plan', result: TripEditResult, snapshot: string, acknowledge: (applied: boolean) => void): void
  (event: 'undo-edit'): void
}>()
const { t } = useI18n()
const chatOpen = ref(false)
const chatInput = ref('')
const chatHistory = ref<ChatMessage[]>([])
const chatLoading = ref(false)
const applying = ref(false)
const proposal = ref<ReplacementProposal | null>(null)
const proposalSnapshot = ref('')
const proposalExpiresAt = ref(0)
const selectedTarget = ref<{day: number; attraction: number; name: string} | null>(null)
const chatMessagesRef = ref<HTMLElement | null>(null)
const quickQuestions = [
  {labelKey:'result.chat.quickPriceLabel',questionKey:'result.chat.quickPriceQuestion'},
  {labelKey:'result.chat.quickSuitabilityLabel',questionKey:'result.chat.quickSuitabilityQuestion'},
  {labelKey:'result.chat.quickMealLabel',questionKey:'result.chat.quickMealQuestion'},
]
const chatPlaceholder = computed(() => props.tripPlan ? t('result.chat.placeholder') : t('result.noTripPlanDesc'))
const distanceText = (distance: number | null) => distance === null ? '—' : distance + ' km'
const scrollChatToBottom = () => nextTick(() => {
  if (chatMessagesRef.value) chatMessagesRef.value.scrollTop = chatMessagesRef.value.scrollHeight
})
watch(chatOpen, open => { if (open) scrollChatToBottom() })
watch(() => props.tripPlan, () => {
  if (proposal.value && JSON.stringify(props.tripPlan) !== proposalSnapshot.value) proposal.value = null
  const target = selectedTarget.value
  if (target && props.tripPlan?.days[target.day]?.attractions[target.attraction]?.name !== target.name) selectedTarget.value = null
}, {deep: true})
const openChatPanel = () => { chatOpen.value = true }
const closeChatPanel = () => { chatOpen.value = false }
const startReplacement = (day: number, attraction: number) => {
  if (chatLoading.value || applying.value || props.editing) return
  const target = props.tripPlan?.days[day]?.attractions[attraction]
  if (!target) return
  proposal.value = null
  selectedTarget.value = {day, attraction, name: target.name}
  chatInput.value = t('result.chatEdit.prompt', {day: day + 1, name: target.name})
  chatOpen.value = true
}
defineExpose({ startReplacement, notifyUndo: () => {
  proposal.value = null
  selectedTarget.value = null
  appendReply(t('result.chatEdit.undone'))
} })
const sendQuickQuestion = (question: string) => { chatInput.value = question; void sendChatMessage() }
const appendReply = (content: string) => {
  chatHistory.value.push({role: 'assistant', content})
  scrollChatToBottom()
}
const sendChatMessage = async () => {
  const text = chatInput.value.trim()
  if (!text || chatLoading.value || applying.value || !props.tripPlan || props.editing) return
  chatHistory.value.push({role: 'user', content: text})
  chatInput.value = ''
  if (/^(撤销|撤回|撤销上次修改|undo)$/i.test(text)) {
    if (props.canUndo) emit('undo-edit')
    else appendReply(t('result.chatEdit.noUndo'))
    return
  }
  const snapshot = JSON.stringify(props.tripPlan)
  proposal.value = null
  chatLoading.value = true
  scrollChatToBottom()
  try {
    const {data} = await axios.post<TripChatResponse>(`${getRuntimeApiBaseUrl()}/api/chat/ask`, {
      message: text, trip_plan: props.tripPlan, history: chatHistory.value.slice(0,-1).slice(-8),
      mode: 'auto', target_day_index: selectedTarget.value?.day, target_attraction_index: selectedTarget.value?.attraction,
      language: getCurrentLocale().split('-')[0],
    }, {timeout: 100000})
    if (!data.success) { appendReply(t('result.chat.replyFallback')); return }
    if (JSON.stringify(props.tripPlan) !== snapshot && data.proposal) { appendReply(t('result.chatEdit.stale')); return }
    appendReply(data.reply)
    if (data.proposal) {
      proposal.value = data.proposal
      proposalSnapshot.value = snapshot
      proposalExpiresAt.value = Date.now() + data.proposal.expires_in_seconds * 1000
      // 停留在候选开头，避免将首个候选滚出视野。
      await nextTick()
      const panel = chatMessagesRef.value?.querySelector<HTMLElement>('.replacement-preview')
      if (panel && chatMessagesRef.value) chatMessagesRef.value.scrollTop = panel.offsetTop - chatMessagesRef.value.offsetTop
    }
  } catch (error) {
    appendReply(axios.isAxiosError(error) && typeof error.response?.data?.detail === 'string' ? error.response.data.detail : t('result.chat.networkError'))
  } finally { chatLoading.value = false }
}
const applyReplacement = async (candidateId: string) => {
  if (!proposal.value || !props.tripPlan || props.editing || applying.value) return
  if (Date.now() >= proposalExpiresAt.value || JSON.stringify(props.tripPlan) !== proposalSnapshot.value) {
    proposal.value = null
    appendReply(t('result.chatEdit.stale'))
    return
  }
  const current = proposal.value
  const snapshot = proposalSnapshot.value
  applying.value = true
  try {
    const {data} = await axios.post<TripEditResult>(`${getRuntimeApiBaseUrl()}/api/chat/edit/apply`, {
      proposal_id: current.id, candidate_id: candidateId, trip_plan: props.tripPlan, language: getCurrentLocale().split('-')[0],
    }, {timeout: 20000})
    if (props.editing || JSON.stringify(props.tripPlan) !== snapshot) { appendReply(t('result.chatEdit.stale')); proposal.value = null; return }
    const accepted = await new Promise<boolean>(resolve => emit('apply-plan', data, snapshot, resolve))
    proposal.value = null
    if (accepted) {
      selectedTarget.value = null
      appendReply(data.reply + '\n' + t('result.chatEdit.sessionOnly'))
    } else appendReply(t('result.chatEdit.stale'))
  } catch (error) {
    proposal.value = null
    appendReply(axios.isAxiosError(error) && typeof error.response?.data?.detail === 'string' ? error.response.data.detail : t('result.chatEdit.applyFailed'))
  } finally { applying.value = false }
}
</script>
<style scoped>
.ai-chat-floating { position: fixed; right: 24px; bottom: 24px; z-index: 1000; }
.chat-launcher { display: flex; align-items: center; gap: 9px; border: 1px solid #38816b; background: #1d6b58; color: white; border-radius: 12px; padding: 13px 19px; font-size: 13px; box-shadow: 0 8px 24px #1f593b26; }.chat-launcher > span { font-size: 23px; line-height: 1; }
.chat-panel { width: 430px; max-width: calc(100vw - 28px); background: white; border: 1px solid #dae5d3; border-radius: 18px; box-shadow: 0 16px 80px #193e302e; overflow: hidden; }
.chat-panel header { padding: 16px; border-bottom: 1px solid #e8eddf; display: flex; justify-content: space-between; align-items: center; }.chat-panel header > div { display: flex; align-items: center; gap: 9px; }.chat-panel header strong { font-size: 14px; font-weight: 600; }.chat-avatar { background: #e8f3e7; border-radius: 8px; padding: 5px 10px; color: #65965e; font-size: 20px; }.chat-close-btn { border: 0; background: #f3f6ed; color: #7a906e; width: 28px; height: 28px; border-radius: 6px; font-size: 20px; }
.chat-history { height: 450px; max-height: 55vh; overflow-y: auto; padding: 18px; display: flex; flex-direction: column; gap: 12px; }.chat-empty p { color: #809272; font-size: 13px; line-height: 1.9; }.chat-suggestions { display: flex; flex-direction: column; align-items: flex-start; gap: 9px; margin-top: 20px; }.chat-suggestions button { border: 1px solid #e1ead8; background: #f8faf4; color: #628053; border-radius: 8px; padding: 9px 12px; font-size: 12px; }
.chat-msg { padding: 12px 14px; border-radius: 10px; font-size: 13px; line-height: 1.8; white-space: pre-wrap; overflow-wrap: anywhere; max-width: 94%; }.chat-msg.assistant { background: #f2f6ec; color: #486a3b; align-self: flex-start; }.chat-msg.user { background: #1d6b58; color: white; align-self: flex-end; }
.chat-compose { border-top: 1px solid #e5ecdc; padding: 14px; display: flex; align-items: flex-end; gap: 10px; }.chat-compose textarea { min-width: 0; flex: 1; resize: none; border: 0; padding: 7px; font-size: 12px; line-height: 1.7; background: #fafbf7; border-radius: 8px; }.chat-compose button { background: #1d6b58; border: 0; border-radius: 8px; color: white; padding: 9px 12px; white-space: nowrap; font-size: 12px; }
@media (max-width: 600px) { .ai-chat-floating { right: 14px; bottom: 16px; } }

.edit-target { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; font-size: 12px; background: #eef5e9; color: #3e6c48; }.edit-target button { border: 0; background: transparent; font-size: 18px; color: inherit; }.editing-hint { padding: 10px 16px; font-size: 12px; background: #fff7e9; }
.replacement-preview { font-size: 12px; }.proposal-heading { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 10px; }.proposal-heading button { border: 0; background: transparent; color: #6c7d60; }.replacement-preview > p { font-size: 11px; color: #7b8c6f; line-height: 1.7; margin: 5px 0; }.replacement-card { border: 1px solid #dce7d5; border-radius: 10px; padding: 14px; margin-top: 12px; background: #fafcf6; }.replacement-card h3 { font-size: 15px; margin: 0 0 6px; color: #2b5738; }.replacement-card p { font-size: 11px; color: #75866a; line-height: 1.7; margin: 0 0 10px; }.replacement-card dl { margin: 10px 0; }.replacement-card dl div { display: flex; justify-content: space-between; gap: 8px; margin: 6px 0; }.replacement-card dt { color: #87947a; font-size: 11px; }.replacement-card dd { margin: 0; font-size: 11px; }.replacement-card a { font-size: 11px; }.apply-replacement { margin-top: 12px; border: 0; padding: 10px; border-radius: 7px; width: 100%; background: #1d6b58; color: white; font-size: 12px; }.replacement-card .candidate-warning { color: #9a6b34; margin-top: 10px; }.proposal-warnings { padding-left: 18px; color: #819273; font-size: 10px; line-height: 1.8; }.proposal-storage { border-top: 1px solid #e1e9d8; padding-top: 8px; }.chat-undo { margin: 0 18px 10px; padding: 8px 12px; border: 1px solid #cbdcc0; border-radius: 7px; background: #f4f8ee; color: #486f40; font-size: 12px; }
</style>
