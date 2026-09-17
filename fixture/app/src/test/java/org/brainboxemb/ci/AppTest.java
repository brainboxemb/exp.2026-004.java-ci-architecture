package org.brainboxemb.ci;

import org.junit.Test;
import static org.junit.Assert.assertEquals;

public class AppTest {
    @Test
    public void combinesBothFeatures() {
        assertEquals("core-a+core-b", App.message());
    }
}
