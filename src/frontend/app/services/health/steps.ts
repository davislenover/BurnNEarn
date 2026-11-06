import { Platform } from "react-native";

export class StepTrackingError extends Error {
    constructor(message: string) {
        super(message);
        this.name = "StepTrackingError";
    }
}

/**
 * Reads steps from local midnight to the time of this call.
 * Call only after the user acknowledges the health notice; this may ask for consent.
 */
export async function getTodaysSteps(): Promise<number> {
    // Use the phone's local calendar day, rather than the last 24 hours.
    const endDate = new Date();
    const startDate = new Date(endDate);
    startDate.setHours(0, 0, 0, 0);

    if (Platform.OS === "android") {
        // Load the Android library only on Android, then connect to Health Connect.
        const healthConnect = await import("react-native-health-connect");

        if (!(await healthConnect.initialize())) {
            throw new StepTrackingError("Health Connect is unavailable. Install or update it on your phone.");
        }

        // Reuse existing read access; ask the user only when it is missing.
        const isStepReadPermission = (permission: { recordType: string; accessType: string }) =>
            permission.recordType === "Steps" && permission.accessType === "read";

        let canReadSteps = (await healthConnect.getGrantedPermissions()).some(isStepReadPermission);
        if (!canReadSteps) {
            const permissions = await healthConnect.requestPermission([
                { accessType: "read", recordType: "Steps" },
            ]);
            canReadSteps = permissions.some(isStepReadPermission);
        }
        if (!canReadSteps) {
            throw new StepTrackingError("Allow access to steps in Health Connect to read your daily total.");
        }

        // Request the stored total from midnight to now. Health Connect handles aggregation.
        const result = await healthConnect.aggregateRecord({
            recordType: "Steps",
            timeRangeFilter: {
                operator: "between",
                startTime: startDate.toISOString(),
                endTime: endDate.toISOString(),
            },
        });
        // A successful query with no step data counts as zero.
        return result.COUNT_TOTAL ?? 0;
    }

    if (Platform.OS === "ios") {
        const { Pedometer } = await import("expo-sensors");

        // Expo Pedometer uses motion/fitness permission on iPhone.
        let permission = await Pedometer.getPermissionsAsync();
        if (!permission.granted && permission.canAskAgain) {
            permission = await Pedometer.requestPermissionsAsync();
        }
        if (!permission.granted) {
            throw new StepTrackingError(
                permission.canAskAgain
                    ? "Allow motion and fitness access to read your daily steps."
                    : "Enable motion and fitness access for this app in your phone settings.",
            );
        }

        // Permission alone does not guarantee that a step counter is available.
        if (!(await Pedometer.isAvailableAsync())) {
            throw new StepTrackingError("This device does not have an available step counter.");
        }

        // Read recorded steps for today's range in one call; no live subscription is needed.
        const result = await Pedometer.getStepCountAsync(startDate, endDate);
        return result.steps;
    }

    throw new StepTrackingError("Reading steps requires an Android phone or iPhone.");
}
