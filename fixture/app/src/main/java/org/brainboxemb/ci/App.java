package org.brainboxemb.ci;

public final class App {
    private App() {}

    public static String message() {
        String featureA = FeatureA.value();
        String featureB = FeatureB.value();
        return featureA + "+" + featureB;
    }

    public static void main(String[] args) {
        System.out.println(message());
    }
}
