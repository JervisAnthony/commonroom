import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
type Props = {
  label: string;
  detail: string;
  selected: boolean;
  disabled: boolean;
  onPress: () => void;
};
export function PreviewChoice({ label, detail, selected, disabled, onPress }: Props) {
  const [focused, setFocused] = useState(false);
  return (<Pressable accessibilityRole="radio" accessibilityLabel={`${label}. ${detail}`} accessibilityState={{ checked: selected, disabled }} disabled={disabled} onPress={onPress} onFocus={() => setFocused(true)} onBlur={() => setFocused(false)} style={({ pressed }) => [styles.choice, selected && styles.selected, disabled && styles.disabled, pressed && styles.pressed, focused && styles.focused]}>
    <View style={styles.copy}>
      <Text style={styles.label}>{label}</Text>
      <Text style={styles.detail}>{detail}</Text>
    </View>
    <View style={styles.selection} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <View style={[styles.radio, selected && styles.checked]} />
      {selected && <Text style={styles.selectedText}>Selected</Text>}
    </View>
  </Pressable>);
}
const styles = StyleSheet.create({
  choice: {
    minHeight: 72, flexDirection: 'row', alignItems: 'center', gap: 12, padding: 16, borderWidth: 1, borderColor: '#B3BAAC', borderRadius: 14, backgroundColor: '#FFFCF5'
  },
  selected: {
    borderColor: '#35543F', borderWidth: 2, backgroundColor: '#E8EDE3', padding: 15
  },
  disabled: {
    opacity: 0.7
  },
  pressed: {
    backgroundColor: '#DFE6D9'
  },
  focused: {
    borderColor: '#805022', borderWidth: 3, padding: 14
  },
  copy: {
    flex: 1, minWidth: 0
  },
  label: {
    color: '#243629', fontSize: 17, fontWeight: '600'
  },
  detail: {
    color: '#4A554A', fontSize: 14, marginTop: 5
  },
  selection: {
    alignItems: 'center', gap: 5, flexShrink: 1
  },
  radio: {
    width: 22, height: 22, borderWidth: 2, borderColor: '#536451', borderRadius: 11
  },
  checked: {
    borderWidth: 7, borderColor: '#35543F'
  },
  selectedText: {
    color: '#35543F', fontSize: 11, fontWeight: '700'
  }
});
