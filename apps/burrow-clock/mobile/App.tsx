import { StatusBar } from 'expo-status-bar';
import { useEffect, useState, type ReactNode } from 'react';
import { AccessibilityInfo, AppState, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { PreviewChoice } from './src/components/PreviewChoice';
import {
  EXAMPLE_CONTACTS, PREVIEW_DURATIONS, advancePreview, beginPreview, createPreviewState, endPreview,
  type ExampleRecipient, type PreviewScope,
} from './src/preview-session';

const scopes: {
  value: PreviewScope;
  title: string;
  description: string;
}[] = [
  { value: 'PRESENCE', title: 'Presence', description: 'A hypothetical general presence category.' },
  { value: 'APPROXIMATE', title: 'Approximate', description: 'A hypothetical broad area, with less detail.' },
  { value: 'PRECISE', title: 'Precise', description: 'The most sensitive hypothetical scope: an exact location.' },
];

export default function App() {
  const [recipient, setRecipient] = useState<ExampleRecipient | null>(null);
  const [scope, setScope] = useState<PreviewScope | null>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const [preview, setPreview] = useState(createPreviewState);
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    if (preview.phase !== 'running')
      return;
    function refresh() {
      const now = Date.now();
      setNowMs(now);
      setPreview(current => advancePreview(current, now));
    }
    // Local presentation clock only; no server polling or background task.
    const timer = setInterval(refresh, 1000);
    const subscription = AppState.addEventListener('change', state => {
      if (state === 'active')
        refresh();
    });
    return () => { clearInterval(timer); subscription.remove(); };
  }, [preview.phase]);
  const current = advancePreview(preview, nowMs);
  const running = current.phase === 'running';
  const completed = current.phase === 'cancelled' || current.phase === 'expired';
  const contact = EXAMPLE_CONTACTS.find(example => example.id === recipient);
  const durationLabel = PREVIEW_DURATIONS.find(option => option.seconds === duration)?.label;
  const ready = recipient !== null && scope !== null && duration !== null;
  const remaining = running ? Math.max(0, Math.ceil((current.session.expiresAtMs - nowMs) / 1000)) : 0;
  const remainingLabel = remaining >= 60 ? `${Math.ceil(remaining / 60)} min remaining` : `${remaining} sec remaining`;
  const statusTitle = running ? 'Preview session running — no information is shared.'
    : current.phase === 'cancelled' ? 'Preview ended. No information was shared.'
      : current.phase === 'expired' ? 'Preview expired. No information was shared.'
        : 'No preview session running.';
  useEffect(() => {
    if (current.phase !== 'idle')
      AccessibilityInfo.announceForAccessibility(statusTitle);
  }, [current.phase, statusTitle]);
  function start() {
    if (!recipient || !scope || duration === null)
      return;
    const now = Date.now();
    const selection = { recipientId: recipient, scope, durationSeconds: duration, direction: 'outgoing' as const };
    setNowMs(now);
    setPreview(previous => advancePreview(previous, now).phase === 'running' ? previous : beginPreview(previous, selection, now));
  }
  function end() {
    const now = Date.now();
    setNowMs(now);
    setPreview(previous => endPreview(previous, now));
  }
  return (<SafeAreaProvider>
    <SafeAreaView style={styles.screen}>
      <StatusBar style="dark" />
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.brandRow}>
          <View style={styles.brandCopy}>
            <Text style={styles.brand}>COMMONROOM</Text>
            <Text accessibilityRole="header" style={styles.title}>The Burrow Clock</Text>
          </View>
          <View style={styles.clock} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
            {Array.from({ length: 12 }, (_, i) => <View key={i} style={[styles.clockTick, { transform: [{ rotate: `${i * 30}deg` }, { translateY: -21 }] }]} />)}
            <View style={styles.clockHour} />
            <View style={styles.clockMinute} />
            <View style={styles.clockPin} />
          </View>
        </View>

        <View style={styles.hero}>
          <Text style={styles.heroEyebrow}>YOUR PRIVACY, AT YOUR PACE</Text>
          <Text accessibilityRole="header" style={styles.heroTitle}>Your circle.{'\n'}Your choice.</Text>
          <Text style={styles.heroBody}>A little space to explore consent, with nothing to share and no one to track.</Text>
          <View style={styles.offBadge}>
            <Text style={styles.offText}>Location sharing is off</Text>
          </View>
        </View>

        <View style={styles.notice}>
          <Text style={styles.noticeTitle}>Demo preview — not connected</Text>
          <Text style={styles.body}>All contacts are fictional examples. This app does not access location, connect to accounts, or send information to anyone.</Text>
        </View>

        <View style={styles.explanation}>
          <Text accessibilityRole="header" style={styles.sectionTitle}>Consent goes one way.</Text>
          <Text style={styles.body}>A choice from you to one recipient never turns on the reverse direction. Each person would need to make their own explicit choice.</Text>
          <Text style={styles.small}>Here, it is only a simulation. There are no real friendships or consent grants.</Text>
        </View>

        <View style={styles.sectionHeading}>
          <Text style={styles.eyebrow}>THE PRACTICE NOTEBOOK</Text>
          <Text accessibilityRole="header" style={styles.previewTitle}>Explore a consent preview</Text>
          <Text style={styles.body}>Choose each setting, review it, then explicitly start a simulated session. Nothing starts automatically.</Text>
        </View>

        <Section step="01" title="Choose an example recipient">
          <View accessibilityRole="radiogroup" accessibilityLabel="Fictional preview recipient" style={styles.options}>
            {EXAMPLE_CONTACTS.map(example => <PreviewChoice key={example.id} label={example.label} detail="Fictional contact · example only" selected={recipient === example.id} disabled={running} onPress={() => setRecipient(example.id)} />)}
          </View>
        </Section>

        <Section step="02" title="Choose a hypothetical scope">
          <View accessibilityRole="radiogroup" accessibilityLabel="Hypothetical disclosure scope" style={styles.options}>
            {scopes.map(option => <PreviewChoice key={option.value} label={`${option.title} · ${option.value}`} detail={option.description} selected={scope === option.value} disabled={running} onPress={() => setScope(option.value)} />)}
          </View>
          {scope === 'PRECISE' && <View style={styles.warning} accessibilityRole="alert">
            <Text style={styles.warningTitle}>Precise deserves extra care</Text>
            <Text style={styles.warningBody}>In a connected experience this could disclose exact location. This preview never accesses or shares location.</Text>
          </View>}
        </Section>

        <Section step="03" title="Choose a finite duration">
          <Text style={styles.small}>The simulation expires automatically. You can also end it immediately.</Text>
          <View accessibilityRole="radiogroup" accessibilityLabel="Preview duration" style={styles.options}>
            {PREVIEW_DURATIONS.map(option => <PreviewChoice key={option.seconds} label={option.label} detail={`${option.seconds} seconds · finite preview`} selected={duration === option.seconds} disabled={running} onPress={() => setDuration(option.seconds)} />)}
          </View>
        </Section>

        <View style={styles.review}>
          <Text style={styles.eyebrow}>04 · BEFORE YOU BEGIN</Text>
          <Text accessibilityRole="header" style={styles.sectionTitle}>{completed ? 'Review your next simulation' : 'Review your simulation'}</Text>
          {completed && <Text style={styles.body}>These editable settings are for your next simulated run. The previous preview is complete. Nothing starts until you explicitly start a fresh preview.</Text>}
          <SummaryRow label="From" value="This device’s local preview" />
          <SummaryRow label="To" value={contact?.label ?? 'Choose an example recipient'} />
          <SummaryRow label="Direction" value="One way · outgoing preview" />
          <SummaryRow label="Scope" value={scope ?? 'Choose a hypothetical scope'} />
          <SummaryRow label="Duration" value={durationLabel ?? 'Choose a finite duration'} />

          <View accessibilityLiveRegion="polite" accessibilityRole="text" style={[styles.sessionStatus, running && styles.runningStatus]}>
            <Text style={styles.sessionTitle}>{statusTitle}</Text>
            <Text style={styles.body}>{running ? 'Location sharing is still off. Settings are locked for this simulation. End it before choosing different settings.' : 'Location sharing is still off. A new preview needs another explicit start.'}</Text>
          </View>
          {running && <Text style={styles.countdown} accessibilityLabel={`Simulated preview, ${remainingLabel}`}>{remainingLabel} · simulation only</Text>}
          {running ? <ActionButton title="End simulated preview" hint="Immediately ends only this local simulation. Location sharing remains off." onPress={end} secondary /> : <ActionButton title={current.phase === 'idle' ? 'Start simulated preview' : 'Start a fresh simulated preview'} hint="Starts an in-memory demonstration only. No information is shared." onPress={start} disabled={!ready} />}
          {!ready && !running && <Text style={styles.small}>Select a recipient, scope and duration to continue.</Text>}
          <Text style={styles.small}>Closing or restarting the app clears this local preview. No account or real sharing permission is created.</Text>
        </View>

        <View style={styles.footer}>
          <Text style={styles.footerTitle}>Private by default. Always your choice.</Text>
          <Text style={styles.small}>An original Commonroom preview. No location permissions, real contacts, presence observations or network connection.</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  </SafeAreaProvider>);
}
function Section({ step, title, children }: {
  step: string;
  title: string;
  children: ReactNode;
}) {
  return <View style={styles.section}>
    <Text style={styles.eyebrow}>{step} · PREVIEW SETTINGS</Text>
    <Text accessibilityRole="header" style={styles.sectionTitle}>{title}</Text>{children}</View>;
}
function SummaryRow({ label, value }: {
  label: string;
  value: string;
}) {
  return <View style={styles.summaryRow}>
    <Text style={styles.summaryLabel}>{label}</Text>
    <Text style={styles.summaryValue}>{value}</Text>
  </View>;
}
function ActionButton({ title, hint, onPress, disabled = false, secondary = false }: {
  title: string;
  hint: string;
  onPress: () => void;
  disabled?: boolean;
  secondary?: boolean;
}) {
  const [focused, setFocused] = useState(false);
  return <Pressable accessibilityRole="button" accessibilityLabel={title} accessibilityHint={hint} accessibilityState={{ disabled }} disabled={disabled} onPress={onPress} onFocus={() => setFocused(true)} onBlur={() => setFocused(false)} style={({ pressed }) => [styles.button, secondary && styles.secondaryButton, disabled && styles.disabledButton, pressed && !disabled && styles.pressedButton, focused && styles.focusedButton]}>
    <Text style={[styles.buttonText, secondary && styles.secondaryButtonText, disabled && styles.disabledButtonText]}>{title}</Text>
  </Pressable>;
}
const styles = StyleSheet.create({
  screen: {
    flex: 1, backgroundColor: '#F7F3EA'
  },
  content: {
    flexGrow: 1, padding: 20, width: '100%', maxWidth: 640, alignSelf: 'center', gap: 24
  },
  brandRow: {
    flexDirection: 'row', alignItems: 'center', gap: 16, marginTop: 8
  },
  brandCopy: {
    flex: 1, minWidth: 0
  },
  brand: {
    color: '#536451', fontSize: 11, fontWeight: '700', letterSpacing: 3, marginBottom: 7
  },
  title: {
    color: '#243629', fontSize: 27, fontFamily: Platform.select({ ios: 'Georgia', android: 'serif' })
  },
  clock: {
    width: 56, height: 56, borderRadius: 28, borderWidth: 1, borderColor: '#805D30', backgroundColor: '#EFE6D3'
  },
  clockTick: {
    position: 'absolute', top: 25, left: 26, width: 2, height: 4, backgroundColor: '#805D30'
  },
  clockHour: {
    position: 'absolute', width: 3, height: 15, top: 16, left: 22, backgroundColor: '#35543F', transform: [{ rotate: '-40deg' }]
  },
  clockMinute: {
    position: 'absolute', width: 2, height: 20, top: 8, left: 27, backgroundColor: '#35543F'
  },
  clockPin: {
    position: 'absolute', width: 6, height: 6, borderRadius: 3, top: 25, left: 25, backgroundColor: '#35543F'
  },
  hero: {
    padding: 24, borderRadius: 24, backgroundColor: '#243F30', borderWidth: 1, borderColor: '#49634A'
  },
  heroEyebrow: {
    color: '#E6D1A3', fontSize: 10, fontWeight: '700', letterSpacing: 2
  },
  heroTitle: {
    color: '#FFF9EC', fontSize: 40, fontFamily: Platform.select({ ios: 'Georgia', android: 'serif' }), marginTop: 16, marginBottom: 16
  },
  heroBody: {
    color: '#E3EADF', fontSize: 16
  },
  offBadge: {
    marginTop: 24, borderRadius: 12, backgroundColor: '#E8EDE3', padding: 12, alignSelf: 'flex-start'
  },
  offText: {
    color: '#243629', fontSize: 15, fontWeight: '700'
  },
  notice: {
    backgroundColor: '#E8EDE3', borderRadius: 16, padding: 18, gap: 8, borderWidth: 1, borderColor: '#BAC6B3'
  },
  noticeTitle: {
    color: '#243629', fontSize: 17, fontWeight: '700'
  },
  body: {
    color: '#4A554A', fontSize: 16
  },
  small: {
    color: '#4A554A', fontSize: 14, marginTop: 10
  },
  explanation: {
    paddingHorizontal: 4, gap: 8
  },
  sectionHeading: {
    borderTopWidth: 1, borderColor: '#CBCBBB', paddingTop: 24, gap: 10
  },
  eyebrow: {
    color: '#69512E', fontSize: 10, fontWeight: '700', letterSpacing: 1.5
  },
  sectionTitle: {
    color: '#243629', fontSize: 23, fontFamily: Platform.select({ ios: 'Georgia', android: 'serif' }), marginBottom: 4
  },
  previewTitle: {
    color: '#243629', fontSize: 30, fontFamily: Platform.select({ ios: 'Georgia', android: 'serif' })
  },
  section: {
    gap: 12
  },
  options: {
    gap: 10
  },
  warning: {
    borderRadius: 12, borderWidth: 1, borderColor: '#9A753F', backgroundColor: '#F4E6CC', padding: 16, gap: 6
  },
  warningTitle: {
    color: '#5F3E17', fontSize: 16, fontWeight: '700'
  },
  warningBody: {
    color: '#5F3E17', fontSize: 15
  },
  review: {
    backgroundColor: '#FFFCF5', borderWidth: 1, borderColor: '#B3BAAC', borderRadius: 20, padding: 18, gap: 12
  },
  summaryRow: {
    borderBottomWidth: 1, borderColor: '#DEDCCF', paddingBottom: 12, gap: 4
  },
  summaryLabel: {
    color: '#536451', fontSize: 12, fontWeight: '700'
  },
  summaryValue: {
    color: '#243629', fontSize: 16
  },
  sessionStatus: {
    backgroundColor: '#EFEDE4', borderRadius: 12, padding: 16, gap: 8
  },
  runningStatus: {
    backgroundColor: '#E8EDE3'
  },
  sessionTitle: {
    color: '#243629', fontSize: 17, fontWeight: '700'
  },
  countdown: {
    color: '#35543F', fontSize: 15, fontWeight: '600'
  },
  button: {
    minHeight: 52, borderRadius: 12, backgroundColor: '#35543F', padding: 16, borderWidth: 2, borderColor: '#35543F', alignItems: 'center', justifyContent: 'center'
  },
  buttonText: {
    color: '#FFFDF6', fontSize: 16, fontWeight: '700', textAlign: 'center'
  },
  secondaryButton: {
    backgroundColor: '#FFFCF5', borderColor: '#805022'
  },
  secondaryButtonText: {
    color: '#5F3E17'
  },
  disabledButton: {
    backgroundColor: '#E4E5DA', borderColor: '#CBCBBB'
  },
  disabledButtonText: {
    color: '#626B60'
  },
  pressedButton: {
    opacity: 0.8
  },
  focusedButton: {
    borderColor: '#BA8E4F', borderWidth: 3, padding: 15
  },
  footer: {
    borderTopWidth: 1, borderColor: '#CBCBBB', paddingTop: 20, paddingBottom: 24
  },
  footerTitle: {
    color: '#35543F', fontSize: 15, fontWeight: '600'
  }
});
