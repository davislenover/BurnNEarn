import { ScrollView, StyleSheet, Text, View } from 'react-native';

export default function DemoScreen() {
  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.title}>FitFolio</Text>

      <View style={styles.summary}>
        {/* Steps box — sample value */}
        <View style={styles.card}>
          <Text style={styles.label}>Today's steps</Text>
          <Text style={styles.number}>6,840</Text>
          <Text style={styles.caption}>steps today</Text>
        </View>

        {/* Balance box sample value */}
        <View style={styles.card}>
          <Text style={styles.label}>Balance</Text>
          <Text style={styles.number} numberOfLines={1} adjustsFontSizeToFit>$1,000
          </Text>
          <Text style={styles.caption}>virtual credits</Text>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  // Screen spacing and background
  screen: {
    flex: 1,
    backgroundColor: '#F3F4F6',
  },
  content: {
    paddingHorizontal: 20,
    paddingTop: 80,
    paddingBottom: 40,
    gap: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: '600',
    color: '#171D22',
  },

  // Two equal boxes beside each other
  summary: {
    flexDirection: 'row',
    gap: 12,
  },
  card: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 16,
  },

  // Text shared by the steps and balance boxes
  label: {
    fontSize: 14,
    color: '#69737E',
  },
  number: {
    fontSize: 30,
    fontWeight: '600',
    color: '#171D22',
    marginTop: 16,
    marginBottom: 6,
  },
  caption: {
    fontSize: 12,
    color: '#69737E',
  },
});