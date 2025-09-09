official API description:

# API

1. Create a new game: `/new-game?scenario=1&playerId=[playerId]`

Choose scenario 1, 2, or 3. `playerId` identifies you as the player.

Returns:

```
{
  "gameId": UUID,
  "constraints": {
    "attribute": AttributeId,
    "minCount": number
  }[],
  "attributeStatistics": {
    "relativeFrequencies": {
      [attributeId]: number // 0.0-1.0
    },
    "correlations": {
      [attributeId1]: {
        [attributeId2]: number // -1.0-1.0
      }
    }
  }
}
```

2. Get person and make decision: `/decide-and-next?gameId=uuid&personIndex=0&accept=true`

Get the next person in the queue. For the first person (`personIndex`=0), the
accept parameter is optional. For subsequent persons, include `accept=true` or
`accept=false` to make a decision.

Returns:

```
{
  "status": "running",
  "admittedCount": number,
  "rejectedCount": number,
  "nextPerson": {
    "personIndex": number,
    "attributes": { [attributeId]: boolean }
  }
} | {
  "status": "completed",
  "rejectedCount": number,
  "nextPerson": null
} | {
  "status": "failed",
  "reason": string,
  "nextPerson": null
}
```
