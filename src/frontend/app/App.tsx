import { StatusBar } from 'expo-status-bar';
import { Alert, Button, StyleSheet, Text, View } from 'react-native';
import { getTodaysSteps } from "./services/health/steps";

export default function App() {
  function testTodaysSteps() {
    Alert.alert(
      "Health notice",
      "FitFolio does not give medical advice. Consult a health professional before starting a new exercise program.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Continue",
          onPress: () => {
            getTodaysSteps()
              .then(steps => Alert.alert("Today's steps", String(steps)))
              .catch(error => Alert.alert(
                "Could not read steps",
                error instanceof Error ? error.message : "Please try again.",
              ));
          },
        },
      ],
    );
  }

  return (
    <View style={styles.container}>
      <Text>Open up App.tsx to start working on your app!</Text>
      <StatusBar style="auto" />
      {__DEV__ && <Button title="Read today's steps" onPress={testTodaysSteps} />}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
    alignItems: 'center',
    justifyContent: 'center',
  },
});
