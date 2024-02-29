"use client";

import { useEffect, useState } from "react";
import styles from "./page.module.css";
import { Button, Flex, Progress } from "antd";

function buildRequestURL(path: string, base: string = "http://127.0.0.1:8080"): URL {
  return new URL(path, base);
}

export default function Home() {
  const [progress, setProgress] = useState(0);
  const [taskId, setTaskId] = useState<string | null>(null);

  const createPullTask = async () => {
    const result = await fetch(buildRequestURL("/push"), {
      method: "POST",
    }).then((r) => r.json());
    setTaskId(result.task_id);
    return result.task_id;
  };

  useEffect(() => {
    if (taskId === null) { return; }
    setProgress(0);
    // First, we need to create an instance of EventSource and pass the data stream URL as a
    // parameter in its constructor.
    const es = new EventSource(buildRequestURL(`/stream?task_id=${taskId}`));
    // Whenever the connection is established between the server and the client, we'll get notified
    es.onopen = () => console.log(">>> Connection opened!");
    // Made a mistake, or something bad happened on the server? We get notified here
    es.onerror = (e) => console.log("ERROR!", e);
    // This is where we get the messages. The event is an object and we're interested in its `data` property
    es.onmessage = (e) => {
      console.log(">>>", e.data);
      const { progress } = JSON.parse(e.data);
      setProgress(progress);
      if (progress >= 100 - Math.pow(10, -12)) {
        es.close();
      }
    };
    // Whenever we're done with the data stream we must close the connection
    return () => {
      if (es.readyState !== es.CLOSED) {
        es.close();
      }
    };
  }, [taskId]);

  return (
    <main className={styles.main}>
      <div className={styles.center}>
        <Flex vertical>
          <Button
            type="primary"
            style={{ marginBottom: 16 }}
            onClick={createPullTask}
          >
            Click
          </Button>
          <Progress type="circle" percent={progress} />
        </Flex>
      </div>
    </main>
  );
}
