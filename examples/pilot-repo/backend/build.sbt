ThisBuild / scalaVersion := "2.13.12"

lazy val root = (project in file("."))
  .settings(
    name := "dummy-backend",
    libraryDependencies ++= Seq(
      "com.fasterxml.jackson.core" % "jackson-databind" % "2.13.5",
      "org.apache.kafka" % "kafka-clients" % "3.4.0"
    )
  )
