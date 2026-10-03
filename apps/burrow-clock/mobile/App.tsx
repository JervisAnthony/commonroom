import { StatusBar } from 'expo-status-bar';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';

export default function App() {
  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.screen}>
        <StatusBar style="dark" />
        <ScrollView contentContainerStyle={styles.content}>
          <Text style={styles.brand}>COMMONROOM</Text>
          <Text accessibilityRole="header" style={styles.title}>
            The Burrow Clock
          </Text>
          <Text style={styles.subtitle}>
            A private place for the people you choose.
          </Text>
          <View style={styles.notice}>
            <Text style={styles.noticeTitle}>Location sharing is off by default.</Text>
            <Text style={styles.noticeBody}>
              This mobile shell does not request location access or collect location data.
            </Text>
          </View>
        </ScrollView>
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: '#F7F3EA',
  },
  content: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 28,
    width: '100%',
    maxWidth: 560,
    alignSelf: 'center',
  },
  brand: {
    color: '#536451',
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 3,
    marginBottom: 20,
  },
  title: {
    color: '#243629',
    fontSize: 38,
    fontWeight: '700',
    marginBottom: 16,
  },
  subtitle: {
    color: '#4A554A',
    fontSize: 20,
    lineHeight: 29,
    marginBottom: 36,
  },
  notice: {
    backgroundColor: '#E8EDE3',
    borderRadius: 16,
    padding: 20,
  },
  noticeTitle: {
    color: '#243629',
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 8,
  },
  noticeBody: {
    color: '#4A554A',
    fontSize: 15,
    lineHeight: 23,
  },
});
