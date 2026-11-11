import { StyleSheet, Text, View } from 'react-native';

export default function DemoScreen() {
  return (
    /*Screen container with the title at the top*/
    <View style={styles.screen}>
      <Text style={styles.title}>FitFolio</Text>
      
      {/* Today's steps box — fake data for now */}
      <View style={styles.stepsCard}>
        <Text style={styles.stepsLabel}>Today's steps</Text>
        <Text style={styles.stepsNumber}>6,840</Text>
        <Text style={styles.stepsCaption}>steps today</Text>
        </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,                    // Fill the screen
    backgroundColor: '#F3F4F6', // Light grey background
    paddingHorizontal: 20,     // Space on both sides
    paddingTop: 80,             // Space above the title
  },

  title: {
    fontSize: 28,
    fontWeight: '600',
    color: '#171D22',
  },
  stepsCard: {
    width: '48%',
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 20,
    marginTop: 24,
  },

  stepsLabel: {
    fontSize: 14,
    color: '#69737E',
  },

  stepsNumber: {
    fontSize: 32,
    fontWeight: '600',
    color: '#171D22',
    marginTop: 16,
  },

  stepsCaption: {
    fontSize: 12,
    color: '#69737E',
    marginTop: 6,
  },


});